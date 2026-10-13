"""Verificacion del motor de los juegos, ejecutada desde pytest.

El motor es JavaScript, pero su arnes de capturas corre en Node y falla si
algun pixel del cuadro final sale de la paleta. Esta prueba lo invoca para que
el CI lo cubra sin un segundo flujo de trabajo. Si Node no esta instalado se
omite en lugar de fallar.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tools" / "capturas_motor.js"
RECEIVER = ROOT / "tests" / "js" / "recibir.js"


@unittest.skipIf(shutil.which("node") is None, "Node no esta instalado")
class TestEngineHarness(unittest.TestCase):
    def test_frame_stays_inside_palette(self):
        out = ROOT / "results" / "capturas"
        result = subprocess.run(
            ["node", str(HARNESS), str(out)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            # El codigo de salida se revisa abajo para incluir la salida del
            # arnes en el mensaje de falla.
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pixeles fuera de paleta: 0", result.stdout)
        for name in ("motor_dark.png", "motor_light.png", "flor_zoom.png"):
            self.assertTrue((out / name).is_file(), name)


@unittest.skipIf(shutil.which("node") is None, "Node no esta instalado")
class TestBridgeRoundTrip(unittest.TestCase):
    """Los mensajes los genera Python y los interpreta el motor de JavaScript.

    Es la prueba que garantiza que los dos lados del contrato coinciden: la
    pagina y el juego viven en lenguajes distintos, y un nombre de campo mal
    escrito en cualquiera de los dos dejaria al juego sordo sin ningun error.
    """

    def _receive(self, casos: list[list[dict]]) -> list[dict]:
        entrada = json.dumps([{"mensajes": m} for m in casos])
        result = subprocess.run(
            ["node", str(RECEIVER)],
            input=entrada,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_page_messages_are_understood_by_the_engine(self):
        from neurodac.acquisition import Quality, SignalState
        from neurodac.game_page import bridge_payload, idle_payload

        def q(state):
            return Quality(state, 0, 1.0, 0.2, 1.0, 10, 0, 0, None)

        casos = {
            "lista con valor": [bridge_payload(q(SignalState.READY), 63, False)],
            "lista sin valor": [bridge_payload(q(SignalState.READY), None, False)],
            "calibrando": [bridge_payload(q(SignalState.CALIBRATING), 63, False)],
            "simulada": [bridge_payload(q(SignalState.READY), 40, True)],
            "detenida": [bridge_payload(q(SignalState.READY), 63, False), idle_payload()],
        }
        salida = dict(zip(casos, self._receive(list(casos.values())), strict=True))

        self.assertTrue(salida["lista con valor"]["ready"])
        self.assertEqual(salida["lista con valor"]["signal"], 63)
        self.assertFalse(salida["lista sin valor"]["ready"])
        self.assertIsNone(salida["lista sin valor"]["signal"])
        self.assertFalse(salida["calibrando"]["ready"])
        self.assertTrue(salida["simulada"]["simulated"])
        # Tras Detener, el juego deja de correr y olvida el ultimo valor.
        self.assertFalse(salida["detenida"]["ready"])
        self.assertIsNone(salida["detenida"]["signal"])
        for nombre, r in salida.items():
            with self.subTest(caso=nombre):
                self.assertTrue(all(r["aceptados"]))

    def test_foreign_messages_are_ignored(self):
        # Mensajes de extensiones del navegador o de otra pagina.
        (r,) = self._receive([[{"signalValue": 90, "ready": True}]])
        self.assertEqual(r["aceptados"], [False])
        self.assertFalse(r["ready"])

    def test_forwarded_keys_carry_the_source(self):
        # Asi las manda el reenvio de teclas de game_page.
        from neurodac.game_page import BRIDGE_SOURCE

        (r,) = self._receive([[{"source": BRIDGE_SOURCE, "keydown": "ArrowUp"}]])
        self.assertEqual(r["aceptados"], [True])


if __name__ == "__main__":
    unittest.main(verbosity=2)
