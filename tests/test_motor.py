"""Verificacion del motor de los juegos, ejecutada desde pytest.

El motor es JavaScript, pero su arnes de capturas corre en Node y falla si
algun pixel del cuadro final sale de la paleta. Esta prueba lo invoca para que
el CI lo cubra sin un segundo flujo de trabajo. Si Node no esta instalado se
omite en lugar de fallar.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tools" / "capturas_motor.js"


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
