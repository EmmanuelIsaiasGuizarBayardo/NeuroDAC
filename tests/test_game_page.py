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

from neurodac.game_page import GRAPH_POINTS, SIMULATED_NAME, GameSpec

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "games"

SPECS = {
    "jardin": GameSpec(
        prefix="jardin",
        path="/jardin",
        title="Jardin Mental",
        asset="games/jardin.html",
        signal="meditation",
        keys=("ArrowUp", "ArrowDown"),
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
    return {
        node.id
        for node in walk(component)
        if isinstance(getattr(node, "id", None), str)
    }


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
                self.assertEqual(text.count("<script>"), text.count("</script>"))

    def test_asset_url_is_served_by_dash(self):
        for name, spec in SPECS.items():
            with self.subTest(juego=name):
                self.assertEqual(
                    dash.get_asset_url(spec.asset), f"/assets/{spec.asset}"
                )


class TestBridgeContract(unittest.TestCase):
    """Lo que la pagina manda y lo que el juego escucha deben coincidir."""

    def _source(self, spec: GameSpec) -> str:
        return (ASSETS.parent / spec.asset).read_text(encoding="utf-8")

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
                self.assertIn("setReady", source)
                self.assertRegex(source, r"setReady\(false\)")

    def test_declared_keys_are_handled_by_the_javascript(self):
        # Atrapa el desfase entre GameSpec.keys y el manejador del juego.
        for name, spec in SPECS.items():
            source = self._source(spec)
            for key in spec.keys:
                with self.subTest(juego=name, tecla=key):
                    self.assertIn(f"'{key}'", source)

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
            "store",
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
            node
            for node in walk(build(spec)())
            if getattr(node, "id", None) == "compuerta-gate"
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
            node
            for node in walk(build(spec)())
            if getattr(node, "id", None) == "puente-bridge"
        )
        self.assertFalse(store.data["ready"])


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
