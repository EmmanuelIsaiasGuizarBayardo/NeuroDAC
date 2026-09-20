"""Pruebas del contenido divulgativo.

La mas valiosa es la de cobertura: comprueba que para cada banda, cada modo de
vista, cada tipo de senal y cada estado que el codigo puede producir exista un
texto. Sin ella, agregar un estado nuevo se descubre como un hueco en la
pantalla durante una demostracion.

    uv run pytest tests/test_content.py -q
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from neurodac import content as content_module
from neurodac.acquisition import SIGNAL_TYPES, SignalState
from neurodac.content import (
    CONTENT_PATH,
    ContentError,
    band,
    content,
    game,
    render,
    signal,
    state,
    view,
)

BANDS = ("none", "delta", "theta", "alpha", "beta", "gamma")
VIEWS = ("unica", "multi", "superpuesta")
GAMES = ("jardin", "carrera")


class TestFileIsValid(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(CONTENT_PATH.is_file(), f"falta {CONTENT_PATH}")

    def test_file_is_utf8_json(self):
        json.loads(CONTENT_PATH.read_text(encoding="utf-8"))

    def test_declares_its_licence(self):
        # El contenido lleva licencia distinta del codigo; debe decirlo.
        self.assertEqual(content()["licencia"], "CC-BY-4.0")

    def test_declares_its_language(self):
        self.assertEqual(content()["idioma"], "es")


class TestCoverage(unittest.TestCase):
    """Todo lo que el codigo puede pedir tiene que existir en el archivo."""

    def test_every_band_has_text(self):
        for key in BANDS:
            with self.subTest(banda=key):
                entry = band(key)
                self.assertTrue(entry.title.strip())
                self.assertTrue(entry.body.strip())

    def test_multichannel_text_exists(self):
        # Lo usa la vista multicanal, que no es una banda de frecuencia.
        self.assertTrue(band("multicanal").body.strip())

    def test_every_view_has_text(self):
        for key in VIEWS:
            with self.subTest(vista=key):
                self.assertTrue(view(key).body.strip())

    def test_every_signal_type_has_a_description(self):
        # Recorre SIGNAL_TYPES del modulo de adquisicion, no una lista propia.
        for key in SIGNAL_TYPES:
            with self.subTest(senal=key):
                self.assertTrue(signal(key).strip())

    def test_every_signal_state_has_label_and_hint(self):
        for signal_state in SignalState:
            with self.subTest(estado=str(signal_state)):
                label, hint = state(str(signal_state))
                self.assertTrue(label.strip())
                self.assertTrue(hint.strip(), "un estado sin instruccion accionable")

    def test_every_game_has_an_explanation(self):
        for key in GAMES:
            with self.subTest(juego=key):
                title, paragraphs = game(key)
                self.assertTrue(title.strip())
                self.assertGreaterEqual(len(paragraphs), 1)


class TestHintsAreActionable(unittest.TestCase):
    """La instruccion debe decirle al operador que hacer, no solo que pasa."""

    def test_hints_are_not_a_restatement_of_the_label(self):
        for signal_state in SignalState:
            label, hint = state(str(signal_state))
            with self.subTest(estado=str(signal_state)):
                self.assertNotEqual(hint.strip().lower(), label.strip().lower())

    def test_hints_have_enough_substance(self):
        # El estado READY es la excepcion: no hay nada que hacer.
        for signal_state in SignalState:
            if signal_state is SignalState.READY:
                continue
            _, hint = state(str(signal_state))
            with self.subTest(estado=str(signal_state)):
                self.assertGreater(len(hint), 25)


class TestRender(unittest.TestCase):
    def test_plain_text_stays_plain(self):
        pieces = render("sin enfasis")
        self.assertEqual(pieces, ["sin enfasis"])

    def test_emphasis_becomes_a_component(self):
        pieces = render("es *neurofeedback* puro")
        self.assertEqual([type(p).__name__ for p in pieces], ["str", "Em", "str"])
        self.assertEqual(pieces[1].children, "neurofeedback")

    def test_emphasis_at_the_edges(self):
        self.assertEqual(
            [type(p).__name__ for p in render("*inicio* y fin")], ["Em", "str"]
        )
        self.assertEqual(
            [type(p).__name__ for p in render("inicio y *fin*")], ["str", "Em"]
        )

    def test_several_emphases(self):
        pieces = render("*uno* y *dos*")
        self.assertEqual(sum(1 for p in pieces if type(p).__name__ == "Em"), 2)

    def test_empty_string(self):
        self.assertEqual(render(""), [""])

    def test_game_paragraphs_render(self):
        for key in GAMES:
            _, paragraphs = game(key)
            for index, paragraph in enumerate(paragraphs):
                with self.subTest(juego=key, parrafo=index):
                    self.assertTrue(render(paragraph))


class TestFailsLoudly(unittest.TestCase):
    """Un hueco debe fallar con nombre, no aparecer en blanco en pantalla."""

    def test_unknown_band(self):
        with self.assertRaises(ContentError):
            band("ultravioleta")

    def test_unknown_signal(self):
        with self.assertRaises(ContentError):
            signal("telepatia")

    def test_unknown_state(self):
        with self.assertRaises(ContentError):
            state("euforica")

    def test_unknown_game(self):
        with self.assertRaises(ContentError):
            game("ajedrez")

    def test_missing_file(self):
        content_module.content.cache_clear()
        self.addCleanup(content_module.content.cache_clear)
        with (
            mock.patch.object(content_module, "CONTENT_PATH", Path("/no/existe.json")),
            self.assertRaises(ContentError),
        ):
            content()

    def test_malformed_json(self):
        content_module.content.cache_clear()
        self.addCleanup(content_module.content.cache_clear)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            handle.write("{no es json")
            path = Path(handle.name)
        self.addCleanup(path.unlink)

        with (
            mock.patch.object(content_module, "CONTENT_PATH", path),
            self.assertRaises(ContentError),
        ):
            content()

    def test_missing_section(self):
        content_module.content.cache_clear()
        self.addCleanup(content_module.content.cache_clear)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump({"bandas": {}}, handle)
            path = Path(handle.name)
        self.addCleanup(path.unlink)

        with (
            mock.patch.object(content_module, "CONTENT_PATH", path),
            self.assertRaises(ContentError) as caught,
        ):
            content()
        self.assertIn("vistas", str(caught.exception))


class TestNoContentLeftInCode(unittest.TestCase):
    """El contenido salio del codigo y no debe volver a entrar."""

    ROOT = Path(__file__).resolve().parent.parent

    def test_pages_have_no_content_dictionaries(self):
        for page in (self.ROOT / "pages").glob("*.py"):
            source = page.read_text(encoding="utf-8")
            for name in ("EDU", "VIEW_INFO", "SIGNAL_INFO", "EXPLANATION"):
                with self.subTest(pagina=page.name, literal=name):
                    self.assertNotIn(f"\n{name} = ", source)
                    self.assertNotIn(f"\n{name}: ", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestManualIsGenerated(unittest.TestCase):
    """El manual es artefacto generado y no debe editarse a mano."""

    ROOT = Path(__file__).resolve().parent.parent

    def test_manual_matches_the_content_file(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, str(self.ROOT / "tools" / "generar_manual.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"el manual esta desactualizado:\n{result.stdout}{result.stderr}",
        )
