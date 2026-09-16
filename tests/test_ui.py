"""Pruebas de la capa de presentacion.

Solo la mitad pura: traduccion de estado, formateo y decision de compuerta.
Nada de esto necesita navegador, y es justo la logica que decide si una
demostracion se puede rescatar en vivo.

    uv run pytest tests/test_ui.py -q
"""

from __future__ import annotations

import unittest

from neurodac.acquisition import Quality, SignalState
from neurodac.ui import (
    STATE_STYLES,
    PanelIds,
    describe,
    format_age,
    format_rate,
    gate_children,
    render_quality,
)


def make_quality(
    state: SignalState = SignalState.READY,
    *,
    poor_signal: int | None = 0,
    packet_rate_hz: float = 1.0,
    seconds_since_last_packet: float | None = 0.2,
    calibration_progress: float = 1.0,
    packets_ok: int = 10,
    packets_bad_checksum: int = 0,
    bytes_discarded: int = 0,
    error: str | None = None,
) -> Quality:
    return Quality(
        state=state,
        poor_signal=poor_signal,
        packet_rate_hz=packet_rate_hz,
        seconds_since_last_packet=seconds_since_last_packet,
        calibration_progress=calibration_progress,
        packets_ok=packets_ok,
        packets_bad_checksum=packets_bad_checksum,
        bytes_discarded=bytes_discarded,
        error=error,
    )


def flatten(component) -> str:
    """Aplana el arbol de componentes a texto, para poder buscar dentro."""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(flatten(c) for c in component)
    children = getattr(component, "children", None)
    return flatten(children) if children is not None else ""


class TestStateCoverage(unittest.TestCase):
    """Ningun estado puede quedarse sin traduccion."""

    def test_every_state_has_a_style(self):
        for state in SignalState:
            self.assertIn(state, STATE_STYLES)

    def test_every_style_has_an_actionable_hint(self):
        # La pista es lo que convierte el diagnostico en algo que el operador
        # puede hacer; una vacia volveria inutil el indicador.
        for state, style in STATE_STYLES.items():
            with self.subTest(state=state):
                self.assertTrue(style.label)
                self.assertTrue(style.css_class)
                self.assertGreater(len(style.hint), 10)

    def test_describe_matches_the_table(self):
        for state in SignalState:
            self.assertIs(describe(make_quality(state)), STATE_STYLES[state])


class TestFormatting(unittest.TestCase):
    def test_rate_zero(self):
        self.assertEqual(format_rate(0.0), "0 Hz")

    def test_rate_below_ten_keeps_a_decimal(self):
        self.assertEqual(format_rate(1.0), "1.0 Hz")

    def test_rate_above_ten_is_rounded(self):
        self.assertEqual(format_rate(511.6), "512 Hz")

    def test_age_never(self):
        self.assertEqual(format_age(None), "nunca")

    def test_age_subsecond(self):
        self.assertEqual(format_age(0.3), "ahora")

    def test_age_seconds(self):
        self.assertEqual(format_age(4.2), "hace 4 s")

    def test_age_minutes(self):
        self.assertEqual(format_age(180.0), "hace 3 min")


class TestPanelIds(unittest.TestCase):
    def test_ids_carry_the_prefix(self):
        ids = PanelIds("jardin")
        self.assertTrue(ids.connect.startswith("jardin-"))
        self.assertTrue(ids.quality.startswith("jardin-"))

    def test_two_prefixes_never_collide(self):
        campos = (
            "source",
            "port",
            "signal",
            "connect",
            "stop",
            "status",
            "quality",
            "interval",
            "store",
        )
        uno = {getattr(PanelIds("j1"), c) for c in campos}
        dos = {getattr(PanelIds("j2"), c) for c in campos}

        self.assertEqual(len(uno), len(campos))  # sin duplicados internos
        self.assertEqual(uno & dos, set())


class TestGate(unittest.TestCase):
    """La compuerta es lo que impide que el juego corra con datos falsos."""

    def test_open_only_when_ready(self):
        self.assertIsNone(gate_children(make_quality(SignalState.READY)))

    def test_closed_in_every_other_state(self):
        for state in SignalState:
            if state is SignalState.READY:
                continue
            with self.subTest(state=state):
                self.assertIsNotNone(gate_children(make_quality(state)))

    def test_closed_gate_tells_the_visitor_what_happens(self):
        texto = flatten(gate_children(make_quality(SignalState.NO_CONTACT)))
        self.assertIn("Sin contacto", texto)
        self.assertIn("frente", texto)

    def test_calibrating_shows_progress(self):
        hijos = gate_children(
            make_quality(SignalState.CALIBRATING, calibration_progress=0.4)
        )
        clases = [getattr(c, "className", "") for c in hijos]
        self.assertIn("nd-progress", clases)


class TestQualityBlock(unittest.TestCase):
    def test_shows_state_and_rate(self):
        texto = flatten(render_quality(make_quality(packet_rate_hz=512.0)))
        self.assertIn("Lista", texto)
        self.assertIn("512 Hz", texto)

    def test_contact_omitted_while_unknown(self):
        # Sin lectura de poor_signal la metrica no debe inventarse un valor.
        texto = flatten(
            render_quality(make_quality(SignalState.NO_DATA, poor_signal=None))
        )
        self.assertNotIn("Contacto", texto)

    def test_contact_shown_when_known(self):
        texto = flatten(render_quality(make_quality(poor_signal=26)))
        self.assertIn("Contacto", texto)
        self.assertIn("26", texto)

    def test_discarded_only_when_nonzero(self):
        limpio = flatten(render_quality(make_quality(packets_bad_checksum=0)))
        sucio = flatten(render_quality(make_quality(packets_bad_checksum=7)))
        self.assertNotIn("Descartadas", limpio)
        self.assertIn("Descartadas", sucio)

    def test_error_is_surfaced(self):
        texto = flatten(render_quality(make_quality(error="OSError: Access is denied")))
        self.assertIn("Access is denied", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
