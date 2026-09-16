"""Pruebas del servicio de adquisicion.

Ninguna toca hardware. Se usan dos dobles distintos: una fuente guionizada,
que entrega tramas exactas para verificar la maquina de estados, y el
simulador real, para verificar que la ruta completa funciona de punta a punta.

    uv run pytest tests/test_acquisition.py -q
"""

from __future__ import annotations

import time
import unittest
from collections import deque
from unittest import mock

from neurodac.acquisition import (
    DATA_TIMEOUT_S,
    POOR_CONTACT_THRESHOLD,
    WARMUP_S,
    Session,
    SessionRegistry,
    SignalState,
    validate_signal_type,
)
from neurodac.simulator import Scenario, SimulatedSource
from neurodac.thinkgear import Code, build_packet


def wait_until(predicate, timeout: float = 2.0, step: float = 0.005) -> bool:
    """Espera activa breve; devuelve si la condicion se cumplio."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


class ScriptedSource:
    """Fuente que entrega exactamente las tramas que se le empujan."""

    def __init__(self, name: str = "guionizada") -> None:
        self.name = name
        self.opened = False
        self.closed = False
        self._queue: deque[bytes] = deque()

    def push(self, payload: bytes) -> None:
        self._queue.append(build_packet(payload))

    def push_raw_bytes(self, data: bytes) -> None:
        self._queue.append(data)

    def open(self) -> None:
        self.opened = True

    def read(self, timeout: float = 0.1) -> bytes:
        try:
            return self._queue.popleft()
        except IndexError:
            time.sleep(0.002)
            return b""

    def close(self) -> None:
        self.closed = True


class FakeClock:
    """Reloj monotono controlable, para no esperar el calentamiento real."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestSignalTypes(unittest.TestCase):
    def test_scalar_and_band_names_are_valid(self):
        for name in ("raw", "attention", "meditation", "blink", "delta", "mid-gamma"):
            validate_signal_type(name)

    def test_unknown_name_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_signal_type("telepatia")


class TestSessionLifecycle(unittest.TestCase):
    def test_state_before_start(self):
        session = Session(ScriptedSource())
        self.assertIs(session.quality.state, SignalState.DISCONNECTED)
        self.assertFalse(session.is_running)

    def test_start_opens_and_stop_closes(self):
        source = ScriptedSource()
        session = Session(source)
        session.start()
        try:
            self.assertTrue(source.opened)
            self.assertTrue(session.is_running)
        finally:
            session.stop()
        self.assertTrue(source.closed)
        self.assertFalse(session.is_running)

    def test_stop_is_idempotent(self):
        session = Session(ScriptedSource())
        session.start()
        session.stop()
        session.stop()  # no debe lanzar
        self.assertFalse(session.is_running)

    def test_no_data_right_after_start(self):
        session = Session(ScriptedSource())
        session.start()
        try:
            self.assertIs(session.quality.state, SignalState.NO_DATA)
        finally:
            session.stop()


class TestStateMachine(unittest.TestCase):
    """Recorre los estados que el operador debe poder distinguir."""

    def setUp(self):
        self.clock = FakeClock()
        patcher = mock.patch("neurodac.acquisition.time.monotonic", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.source = ScriptedSource()
        self.session = Session(self.source, "attention")
        self.session.start()
        self.addCleanup(self.session.stop)

    def _push_and_wait(self, payload: bytes) -> None:
        before = self.session.quality.packets_ok
        self.source.push(payload)
        wait_until(lambda: self.session.quality.packets_ok > before)

    def _run_seconds(self, seconds: float, poor: int = 0) -> None:
        """Simula operacion normal: la diadema emite eSense a 1 Hz."""
        for _ in range(int(seconds)):
            self.clock.advance(1.0)
            self._push_and_wait(bytes([Code.POOR_SIGNAL, poor]))

    def test_no_contact_is_reported(self):
        self._push_and_wait(bytes([Code.POOR_SIGNAL, 200]))
        quality = self.session.quality
        self.assertIs(quality.state, SignalState.NO_CONTACT)
        self.assertEqual(quality.poor_signal, 200)

    def test_poor_contact_is_reported(self):
        self._push_and_wait(bytes([Code.POOR_SIGNAL, POOR_CONTACT_THRESHOLD + 20]))
        self.assertIs(self.session.quality.state, SignalState.POOR_CONTACT)

    def test_good_contact_starts_calibrating(self):
        self._push_and_wait(bytes([Code.POOR_SIGNAL, 0]))
        quality = self.session.quality
        self.assertIs(quality.state, SignalState.CALIBRATING)
        self.assertLess(quality.calibration_progress, 1.0)

    def test_ready_after_warmup(self):
        self._run_seconds(WARMUP_S + 1)
        quality = self.session.quality
        self.assertIs(quality.state, SignalState.READY)
        self.assertTrue(quality.is_ready)
        self.assertEqual(quality.calibration_progress, 1.0)

    def test_losing_contact_restarts_calibration(self):
        self._run_seconds(WARMUP_S + 1)
        self.assertIs(self.session.quality.state, SignalState.READY)

        # Se despega el electrodo y vuelve a pegarse.
        self._push_and_wait(bytes([Code.POOR_SIGNAL, 200]))
        self._push_and_wait(bytes([Code.POOR_SIGNAL, 0]))

        quality = self.session.quality
        self.assertIs(quality.state, SignalState.CALIBRATING)
        self.assertLess(quality.calibration_progress, 1.0)

    def test_watchdog_detects_silence(self):
        # Este es el caso que antes dejaba el indicador en verde mintiendo.
        self._run_seconds(WARMUP_S + 1)
        self.assertIs(self.session.quality.state, SignalState.READY)

        self.clock.advance(DATA_TIMEOUT_S + 0.1)
        self.assertIs(self.session.quality.state, SignalState.NO_DATA)

    def test_data_gap_restarts_calibration(self):
        # Caida de Bluetooth: al volver, eSense perdio su linea base.
        self._run_seconds(WARMUP_S + 1)
        self.assertIs(self.session.quality.state, SignalState.READY)

        self.clock.advance(DATA_TIMEOUT_S + 20.0)
        self._push_and_wait(bytes([Code.POOR_SIGNAL, 0]))

        quality = self.session.quality
        self.assertIs(quality.state, SignalState.CALIBRATING)
        self.assertLess(quality.calibration_progress, 1.0)


class TestSampleRouting(unittest.TestCase):
    def setUp(self):
        self.source = ScriptedSource()
        self.session = Session(self.source, "attention")
        self.session.start()
        self.addCleanup(self.session.stop)

    def _wait_packets(self, count: int) -> None:
        wait_until(lambda: self.session.quality.packets_ok >= count)

    def test_only_selected_signal_is_buffered(self):
        self.source.push(bytes([Code.ATTENTION, 70]))
        self.source.push(bytes([Code.MEDITATION, 30]))
        self.source.push(bytes([Code.ATTENTION, 75]))
        self._wait_packets(3)

        self.assertEqual(self.session.drain(), [70, 75])

    def test_latest_tracks_every_signal(self):
        self.source.push(bytes([Code.ATTENTION, 70, Code.MEDITATION, 30]))
        wait_until(lambda: self.session.latest("meditation") is not None)

        self.assertEqual(self.session.latest("attention"), 70)
        self.assertEqual(self.session.latest("meditation"), 30)

    def test_poor_signal_tracked_even_when_not_selected(self):
        self.source.push(bytes([Code.POOR_SIGNAL, 26]))
        wait_until(lambda: self.session.quality.poor_signal is not None)

        self.assertEqual(self.session.quality.poor_signal, 26)
        self.assertEqual(self.session.drain(), [])

    def test_drain_empties_the_buffer(self):
        self.source.push(bytes([Code.ATTENTION, 11]))
        self._wait_packets(1)

        self.assertEqual(self.session.drain(), [11])
        self.assertEqual(self.session.drain(), [])

    def test_changing_signal_type_clears_buffer(self):
        self.source.push(bytes([Code.ATTENTION, 70]))
        self._wait_packets(1)

        self.session.set_signal_type("meditation")
        self.assertEqual(self.session.drain(), [])
        self.assertEqual(self.session.signal_type, "meditation")

    def test_band_signal_is_buffered(self):
        self.session.set_signal_type("low-alpha")
        raw = b"".join(v.to_bytes(3, "big") for v in range(1, 9))
        self.source.push(bytes([Code.ASIC_EEG_POWER, 24]) + raw)
        wait_until(lambda: self.session.latest("low-alpha") is not None)

        # low-alpha es la tercera banda del orden del protocolo.
        self.assertEqual(self.session.latest("low-alpha"), 3)
        self.assertEqual(self.session.drain(), [3])

    def test_corrupt_packet_produces_no_samples(self):
        packet = bytearray(build_packet(bytes([Code.ATTENTION, 70])))
        packet[-1] ^= 0xFF
        self.source.push_raw_bytes(bytes(packet))
        wait_until(lambda: self.session.quality.packets_bad_checksum >= 1)

        self.assertEqual(self.session.drain(), [])
        self.assertEqual(self.session.quality.packets_ok, 0)


class TestRegistry(unittest.TestCase):
    """El registro por puerto es lo que impide abrir dos veces el mismo COM."""

    def setUp(self):
        self.registry = SessionRegistry()
        self.addCleanup(self.registry.stop_all)

    def test_same_source_name_reuses_session(self):
        first = self.registry.acquire(ScriptedSource("COM3"), "attention")
        second = self.registry.acquire(ScriptedSource("COM3"), "meditation")

        self.assertIs(first, second)
        self.assertEqual(second.signal_type, "meditation")
        self.assertEqual(self.registry.names, ["COM3"])

    def test_distinct_sources_coexist(self):
        # Es la forma en que entraria una segunda diadema sin tocar el diseno.
        self.registry.acquire(ScriptedSource("COM3"))
        self.registry.acquire(ScriptedSource("COM4"))
        self.assertEqual(sorted(self.registry.names), ["COM3", "COM4"])

    def test_stop_removes_and_closes(self):
        source = ScriptedSource("COM3")
        self.registry.acquire(source)

        self.assertTrue(self.registry.stop("COM3"))
        self.assertTrue(source.closed)
        self.assertEqual(self.registry.names, [])
        self.assertFalse(self.registry.stop("COM3"))

    def test_stop_all_releases_everything(self):
        sources = [ScriptedSource("COM3"), ScriptedSource("COM4")]
        for source in sources:
            self.registry.acquire(source)

        self.registry.stop_all()
        self.assertEqual(self.registry.names, [])
        self.assertTrue(all(s.closed for s in sources))

    def test_failure_to_open_does_not_leave_a_ghost(self):
        class Exploding(ScriptedSource):
            def open(self):
                raise OSError("Access is denied")

        with self.assertRaises(OSError):
            self.registry.acquire(Exploding("COM9"))
        self.assertEqual(self.registry.names, [])


class TestSimulatedSource(unittest.TestCase):
    """Ruta completa: simulador, parser, hilo y sesion."""

    def test_reaches_good_contact_and_delivers_samples(self):
        source = SimulatedSource(seed=7, contact_delay_s=0.0)
        session = Session(source, "raw")
        session.start()
        try:
            ok = wait_until(lambda: len(session.drain()) > 0, timeout=3.0)
            self.assertTrue(ok, "el simulador no entrego muestras crudas")
            wait_until(lambda: session.quality.poor_signal is not None, timeout=3.0)
            self.assertLessEqual(session.quality.poor_signal, POOR_CONTACT_THRESHOLD)
        finally:
            session.stop()

    def test_bad_contact_scenario_never_becomes_ready(self):
        source = SimulatedSource(seed=3, scenario=Scenario.BAD_CONTACT)
        session = Session(source, "attention")
        session.start()
        try:
            wait_until(lambda: session.quality.poor_signal is not None, timeout=3.0)
            self.assertIn(
                session.quality.state,
                (SignalState.NO_CONTACT, SignalState.POOR_CONTACT, SignalState.NO_DATA),
            )
            self.assertFalse(session.quality.is_ready)
        finally:
            session.stop()

    def test_noisy_scenario_is_counted_not_propagated(self):
        source = SimulatedSource(seed=11, scenario=Scenario.NOISY, contact_delay_s=0.0)
        session = Session(source, "raw")
        session.start()
        try:
            wait_until(lambda: session.quality.packets_bad_checksum > 0, timeout=3.0)
            quality = session.quality
            self.assertGreater(quality.packets_bad_checksum, 0)
            self.assertGreater(quality.packets_ok, quality.packets_bad_checksum)
        finally:
            session.stop()

    def test_seed_makes_the_run_reproducible(self):
        def first_samples(seed: int) -> list[float]:
            source = SimulatedSource(seed=seed, contact_delay_s=0.0)
            source.open()
            time.sleep(0.15)
            data = source.read()
            source.close()

            from neurodac.thinkgear import ThinkGearParser

            events = ThinkGearParser().feed(data)
            return [e.value for e in events if e.code == Code.RAW_VALUE][:20]

        self.assertEqual(first_samples(99), first_samples(99))
        self.assertNotEqual(first_samples(99), first_samples(100))


if __name__ == "__main__":
    unittest.main(verbosity=2)
