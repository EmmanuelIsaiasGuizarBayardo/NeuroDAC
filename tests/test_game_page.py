"""Pruebas de las paginas de juego.

Verifican tres cosas: que el layout traiga los componentes que los callbacks
esperan, que la compuerta nazca cerrada, y que la especificacion de Python y
el HTML del juego no se desincronicen. Esa ultima es la que atrapa el error
de agregar una tecla al `GameSpec` y olvidarla en el JavaScript.

    uv run pytest tests/test_game_page.py -q
"""

from __future__ import annotations

import dataclasses
import re
import unittest
from pathlib import Path

import dash

from neurodac.acquisition import Quality, SignalState
from neurodac.game_page import (
    BRIDGE_SOURCE,
    GRAPH_MS,
    GRAPH_POINTS,
    QUALITY_MS,
    SIMULATED_NAME,
    GameSpec,
    bridge_payload,
    idle_payload,
    stopped_outputs,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "games"

#: Scripts que un juego carga por `src`; el contrato puede vivir en ellos.
SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE)


def local_scripts(html_path: Path) -> list[Path]:
    """Scripts locales referenciados por un HTML, en el orden en que se cargan."""
    text = html_path.read_text(encoding="utf-8")
    return [
        (html_path.parent / src).resolve()
        for src in SCRIPT_SRC.findall(text)
        if "://" not in src and not src.startswith("//")
    ]


SPECS = {
    "jardin": GameSpec(
        prefix="jardin",
        path="/jardin",
        title="Jardin Mental",
        asset="games/jardin.html",
        signal="meditation",
        keys=(),
    ),
    "carrera": GameSpec(
        prefix="carrera",
        path="/carrera",
        title="Carrera Neural",
        asset="games/carrera.html",
        signal="attention",
        keys=("ArrowLeft", "ArrowRight", "w", "W", "s", "S"),
    ),
}


def walk(component):
    """Recorre el arbol de componentes de Dash."""
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or hasattr(child, "id"):
            yield from walk(child)


def ids_in(component) -> set[str]:
    return {node.id for node in walk(component) if isinstance(getattr(node, "id", None), str)}


class TestGameSpec(unittest.TestCase):
    def test_spec_is_immutable(self):
        # Una dataclass congelada protege las constantes de juego de que un
        # callback las modifique por accidente en caliente.
        with self.assertRaises(dataclasses.FrozenInstanceError):
            SPECS["jardin"].signal = "attention"

    def test_prefixes_are_distinct(self):
        prefixes = [spec.prefix for spec in SPECS.values()]
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_paths_are_distinct(self):
        paths = [spec.path for spec in SPECS.values()]
        self.assertEqual(len(paths), len(set(paths)))


class TestAssetsExist(unittest.TestCase):
    """El HTML dejo de ser un literal de Python; ahora son archivos."""

    @classmethod
    def setUpClass(cls):
        # `get_asset_url` lee la configuracion global de Dash, asi que
        # necesita una app aunque no se levante el servidor.
        cls.app = dash.Dash(__name__, use_pages=True, pages_folder="")

    def test_every_spec_points_to_a_real_file(self):
        for name, spec in SPECS.items():
            path = ASSETS.parent / spec.asset
            with self.subTest(juego=name):
                self.assertTrue(path.is_file(), f"falta {path}")

    def test_files_are_well_formed_html(self):
        for name, spec in SPECS.items():
            text = (ASSETS.parent / spec.asset).read_text(encoding="utf-8")
            with self.subTest(juego=name):
                self.assertTrue(text.lstrip().startswith("<!DOCTYPE html>"))
                self.assertIn("</html>", text)
                # Una apertura con atributos, como <script src="...">, tambien
                # cuenta; comparar el literal "<script>" fallaria con el motor.
                self.assertEqual(len(re.findall(r"<script\b", text)), text.count("</script>"))

    def test_referenced_scripts_exist(self):
        # Un script local que falta deja el juego en blanco sin error visible.
        for name, spec in SPECS.items():
            for script in local_scripts(ASSETS.parent / spec.asset):
                with self.subTest(juego=name, script=script.name):
                    self.assertTrue(script.is_file(), f"falta {script}")

    def test_asset_url_is_served_by_dash(self):
        for name, spec in SPECS.items():
            with self.subTest(juego=name):
                self.assertEqual(dash.get_asset_url(spec.asset), f"/assets/{spec.asset}")


class TestBridgeContract(unittest.TestCase):
    """Lo que la pagina manda y lo que el juego escucha deben coincidir."""

    def _source(self, spec: GameSpec) -> str:
        """HTML del juego mas los scripts locales que carga.

        El contrato puede vivir en el motor compartido y no en el HTML; leer
        solo el HTML haria fallar estas pruebas sin que el contrato se rompa.
        """
        html_path = ASSETS.parent / spec.asset
        parts = [html_path.read_text(encoding="utf-8")]
        parts += [p.read_text(encoding="utf-8") for p in local_scripts(html_path) if p.is_file()]
        return "\n".join(parts)

    def test_every_game_listens_for_messages(self):
        for name, spec in SPECS.items():
            with self.subTest(juego=name):
                self.assertIn("addEventListener('message'", self._source(spec))

    def test_every_game_handles_the_three_fields(self):
        for name, spec in SPECS.items():
            source = self._source(spec)
            for field in ("signalValue", "theme", "ready"):
                with self.subTest(juego=name, campo=field):
                    self.assertIn(field, source)

    def test_every_game_gates_its_simulation(self):
        # Sin esto la flor se marchita y el rival se despega antes de empezar.
        for name, spec in SPECS.items():
            source = self._source(spec)
            with self.subTest(juego=name):
                # El juego anterior la implementa con setReady(false); los que
                # usan el motor, consultando isReady() antes de avanzar.
                self.assertRegex(source, r"setReady\(false\)|\bisReady\(\)")

    def test_declared_keys_are_handled_by_the_javascript(self):
        # Atrapa el desfase entre GameSpec.keys y el manejador del juego.
        for name, spec in SPECS.items():
            source = self._source(spec)
            for key in spec.keys:
                with self.subTest(juego=name, tecla=key):
                    self.assertIn(f"'{key}'", source)

    def test_declared_key_list_matches_the_spec(self):
        # Un juego sobre el motor declara las teclas que atiende en KEYS_USED;
        # deben ser exactamente las que la pagina le reenvia.
        for name, spec in SPECS.items():
            match = re.search(r"const KEYS_USED = \[([^\]]*)\]", self._source(spec))
            if match is None:
                continue
            declared = set(re.findall(r"'([^']+)'", match.group(1)))
            with self.subTest(juego=name):
                self.assertEqual(declared, set(spec.keys))

    def test_javascript_handles_no_unknown_keys(self):
        """Toda tecla que el juego atiende debe estar declarada en el spec."""
        for name, spec in SPECS.items():
            source = self._source(spec)
            handled = set(re.findall(r"key === '([^']+)'", source))
            declared = set(spec.keys)
            with self.subTest(juego=name):
                self.assertTrue(
                    handled <= declared,
                    f"el JS atiende teclas no declaradas: {handled - declared}",
                )


class TestLayout(unittest.TestCase):
    """El layout debe traer todo lo que los callbacks referencian."""

    @classmethod
    def setUpClass(cls):
        cls.app = dash.Dash(__name__, use_pages=True, pages_folder="")

    def test_layout_has_the_components_callbacks_need(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="prueba",
            path="/prueba",
            title="Prueba",
            asset="games/jardin.html",
            signal="meditation",
            keys=("ArrowUp",),
        )
        found = ids_in(build(spec)())

        for suffix in (
            "frame",
            "gate",
            "graph",
            "bridge",
            "source",
            "port",
            "connect",
            "stop",
            "status",
            "quality",
            "interval",
            "quality-interval",
            "store",
            "sim",
        ):
            with self.subTest(componente=suffix):
                self.assertIn(f"prueba-{suffix}", found)

    def test_gate_starts_visible(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="compuerta",
            path="/compuerta",
            title="Compuerta",
            asset="games/jardin.html",
            signal="meditation",
            keys=(),
        )
        gate = next(
            node for node in walk(build(spec)()) if getattr(node, "id", None) == "compuerta-gate"
        )
        # Sin `d-none`: nace cerrada porque todavia no hay sesion.
        self.assertEqual(gate.className, "nd-gate")

    def test_bridge_starts_not_ready(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="puente",
            path="/puente",
            title="Puente",
            asset="games/carrera.html",
            signal="attention",
            keys=(),
        )
        store = next(
            node for node in walk(build(spec)()) if getattr(node, "id", None) == "puente-bridge"
        )
        self.assertFalse(store.data["ready"])
        self.assertIsNone(store.data["signalValue"])
        self.assertEqual(store.data, idle_payload())

    def test_graph_is_above_the_connection_panel(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="orden",
            path="/orden",
            title="Orden",
            asset="games/jardin.html",
            signal="meditation",
            keys=(),
        )
        order = [getattr(n, "id", None) for n in walk(build(spec)())]
        self.assertLess(order.index("orden-graph"), order.index("orden-connect"))

    def test_two_cadences(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="cadencia",
            path="/cadencia",
            title="Cadencia",
            asset="games/jardin.html",
            signal="meditation",
            keys=(),
        )
        intervals = {
            n.id: n.interval for n in walk(build(spec)()) if type(n).__name__ == "Interval"
        }
        self.assertEqual(intervals["cadencia-interval"], GRAPH_MS)
        self.assertEqual(intervals["cadencia-quality-interval"], QUALITY_MS)
        self.assertLess(GRAPH_MS, QUALITY_MS)

    def test_sim_badge_starts_hidden(self):
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="aviso",
            path="/aviso",
            title="Aviso",
            asset="games/jardin.html",
            signal="meditation",
            keys=(),
        )
        badge = next(n for n in walk(build(spec)()) if getattr(n, "id", None) == "aviso-sim")
        self.assertIn("d-none", badge.className)

    def test_logical_size_matches_the_game(self):
        # Si la pagina declara otra resolucion que la que dibuja el juego, el
        # encuadre ajusta a un tamano equivocado sin que nada falle a la vista.
        import ast

        page = (ASSETS.parent.parent / "pages" / "jardin.py").read_text(encoding="utf-8")
        declared = next(
            ast.literal_eval(kw.value)
            for node in ast.walk(ast.parse(page))
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "logical_size"
        )
        game = (ASSETS / "jardin.js").read_text(encoding="utf-8")
        min_w = int(re.search(r"const MIN_W = (\d+);", game).group(1))
        max_w = int(re.search(r"const MAX_W = (\d+);", game).group(1))
        h = int(re.search(r"const H = (\d+);", game).group(1))
        self.assertEqual(tuple(declared), (min_w, h))
        width_max = next(
            ast.literal_eval(kw.value)
            for node in ast.walk(ast.parse(page))
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "logical_width_max"
        )
        self.assertEqual(width_max, max_w)

    def test_container_exposes_the_logical_size(self):
        from neurodac.game_page import build

        def container(spec):
            return next(
                n
                for n in walk(build(spec)())
                if getattr(n, "className", None) == "game-canvas-container"
            )

        base = {
            "title": "Encuadre",
            "asset": "games/jardin.html",
            "signal": "meditation",
            "keys": (),
        }
        con = container(GameSpec(prefix="enc1", path="/enc1", logical_size=(240, 180), **base))
        attrs = con.to_plotly_json()["props"]
        self.assertEqual((attrs["data-lw"], attrs["data-lh"]), ("240", "180"))
        self.assertEqual(attrs["data-maxh"], "66vh")
        self.assertNotIn("data-lwmax", attrs)
        ancho = container(
            GameSpec(
                prefix="enc3",
                path="/enc3",
                logical_size=(240, 180),
                logical_width_max=360,
                **base,
            )
        )
        self.assertEqual(ancho.to_plotly_json()["props"]["data-lwmax"], "360")
        sin = container(GameSpec(prefix="enc2", path="/enc2", **base))
        self.assertNotIn("data-lw", sin.to_plotly_json()["props"])

    def test_sim_badge_does_not_cover_the_game(self):
        # Encima del lienzo tapaba el marcador de los juegos; va como franja.
        from neurodac.game_page import build

        spec = GameSpec(
            prefix="franja",
            path="/franja",
            title="Franja",
            asset="games/jardin.html",
            signal="meditation",
            keys=(),
        )
        container = next(
            n
            for n in walk(build(spec)())
            if getattr(n, "className", None) == "game-canvas-container"
        )
        inside = [getattr(n, "id", None) for n in walk(container)]
        self.assertIn("franja-frame", inside)
        self.assertNotIn("franja-sim", inside)


def quality(signal_state: SignalState) -> Quality:
    return Quality(
        state=signal_state,
        poor_signal=0,
        packet_rate_hz=1.0,
        seconds_since_last_packet=0.2,
        calibration_progress=1.0,
        packets_ok=10,
        packets_bad_checksum=0,
        bytes_discarded=0,
        error=None,
    )


class TestBridgePayload(unittest.TestCase):
    """Lo que la pagina manda al juego, sin navegador."""

    def test_ready_with_a_value(self):
        payload = bridge_payload(quality(SignalState.READY), 63, simulated=False)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["signalValue"], 63.0)
        self.assertEqual(payload["source"], BRIDGE_SOURCE)

    def test_ready_state_without_a_value_is_not_ready(self):
        # La sesion puede quedar lista antes del primer paquete eSense.
        payload = bridge_payload(quality(SignalState.READY), None, simulated=False)
        self.assertFalse(payload["ready"])
        self.assertIsNone(payload["signalValue"])

    def test_absence_is_never_a_number(self):
        for signal_state in SignalState:
            payload = bridge_payload(quality(signal_state), None, simulated=False)
            with self.subTest(estado=signal_state.value):
                self.assertIsNone(payload["signalValue"])

    def test_not_ready_in_any_other_state(self):
        for signal_state in SignalState:
            if signal_state is SignalState.READY:
                continue
            payload = bridge_payload(quality(signal_state), 70, simulated=False)
            with self.subTest(estado=signal_state.value):
                self.assertFalse(payload["ready"])

    def test_simulated_flag_travels(self):
        self.assertTrue(bridge_payload(quality(SignalState.READY), 70, simulated=True)["simulated"])

    def test_idle_payload(self):
        payload = idle_payload()
        self.assertFalse(payload["ready"])
        self.assertIsNone(payload["signalValue"])
        self.assertFalse(payload["simulated"])

    def test_stop_tells_the_game_to_stop(self):
        # Antes, Detener apagaba la grafica pero el juego conservaba el ultimo
        # ready: true y seguia corriendo con la senal congelada.
        status, fast_off, slow_off, store, bridge, gate, gate_class = stopped_outputs(
            "Detenido.", "secondary"
        )
        self.assertTrue(fast_off)
        self.assertTrue(slow_off)
        self.assertIsNone(store)
        self.assertEqual(bridge, idle_payload())
        self.assertIsNotNone(gate)
        self.assertEqual(gate_class, "nd-gate")


class TestConstants(unittest.TestCase):
    def test_simulated_name_matches_the_simulator_default(self):
        from neurodac.simulator import SimulatedSource

        # Si divergen, cada pagina abriria su propia sesion simulada en vez
        # de compartir una, que es justo lo que el registro debe evitar.
        self.assertEqual(SimulatedSource().name, SIMULATED_NAME)

    def test_graph_window_is_one_second_of_raw(self):
        self.assertEqual(GRAPH_POINTS, 512)


if __name__ == "__main__":
    unittest.main(verbosity=2)
