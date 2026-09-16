"""Diadema simulada.

Genera tramas ThinkGear autenticas, no valores sueltos. Al pasar por el mismo
parser y el mismo hilo lector que la diadema real, lo que se ensaya con el
simulador es la ruta completa y no una version paralela.

Sirve para tres cosas: verificar la interfaz sin hardware, ensayar una
demostracion antes del evento, y probar en automatico los estados de falla que
serian imposibles de provocar a voluntad con la diadema puesta.
"""

from __future__ import annotations

import math
import random
import time
from enum import StrEnum

from .thinkgear import BAND_NAMES, Code, build_packet

__all__ = ["Scenario", "SimulatedSource"]

RAW_HZ = 512.0
ESENSE_HZ = 1.0
RAW_AMPLITUDE = 900.0


class Scenario(StrEnum):
    """Guiones de simulacion."""

    #: Contacto se establece a los 2 s y todo funciona.
    NORMAL = "normal"
    #: El contacto nunca mejora: ejercita el estado de contacto pobre.
    BAD_CONTACT = "mal_contacto"
    #: Funciona y a los 15 s deja de emitir: ejercita el watchdog.
    DROPOUT = "desconexion"
    #: Emite bien pero corrompe una de cada diez tramas.
    NOISY = "ruidosa"


class SimulatedSource:
    """Fuente de bytes que imita a una MindWave Mobile.

    Parameters
    ----------
    name : str, optional
        Identificador con el que la sesion queda registrada.
    seed : int, optional
        Semilla del generador. Con la misma semilla la corrida es identica,
        que es lo que vuelve reproducible una prueba.
    scenario : Scenario, optional
        Guion de fallas a reproducir.
    contact_delay_s : float, optional
        Segundos antes de que el electrodo haga buen contacto.

    Notes
    -----
    `read` no bloquea el tiempo completo: calcula que tramas debieron ocurrir
    desde la llamada anterior y las devuelve juntas. Asi el reloj de la
    simulacion avanza con el reloj real sin depender de dormir con precision.
    """

    def __init__(
        self,
        name: str = "simulada",
        *,
        seed: int | None = 42,
        scenario: Scenario = Scenario.NORMAL,
        contact_delay_s: float = 2.0,
    ) -> None:
        self.name = name
        self.scenario = Scenario(scenario)
        self.contact_delay_s = contact_delay_s
        self._random = random.Random(seed)

        self._started_at: float | None = None
        self._last_read_at: float | None = None
        self._raw_emitted = 0
        self._esense_emitted = 0
        self._packets_built = 0

    # ---------------------------------------------------------------- Source

    def open(self) -> None:
        now = time.monotonic()
        self._started_at = now
        self._last_read_at = now

    def read(self, timeout: float = 0.1) -> bytes:
        if self._started_at is None:
            return b""

        # Ceder un poco de tiempo para no girar en vacio dentro del hilo.
        time.sleep(min(timeout, 0.05))

        now = time.monotonic()
        elapsed = now - self._started_at
        self._last_read_at = now

        if self.scenario is Scenario.DROPOUT and elapsed > 15.0:
            return b""

        chunks: list[bytes] = []

        # Muestras crudas: las que debieron emitirse hasta ahora.
        target_raw = int(elapsed * RAW_HZ)
        for _ in range(max(0, target_raw - self._raw_emitted)):
            self._raw_emitted += 1
            chunks.append(self._raw_packet(self._raw_emitted / RAW_HZ))

        # Paquetes eSense, una vez por segundo.
        target_esense = int(elapsed * ESENSE_HZ)
        while self._esense_emitted < target_esense:
            self._esense_emitted += 1
            chunks.append(self._esense_packet(elapsed))
            chunks.append(self._bands_packet())

        return b"".join(chunks)

    def close(self) -> None:
        self._started_at = None

    # --------------------------------------------------------------- tramas

    def _emit(self, payload: bytes) -> bytes:
        """Arma la trama y, en el escenario ruidoso, corrompe una de diez."""
        packet = bytearray(build_packet(payload))
        self._packets_built += 1
        if self.scenario is Scenario.NOISY and self._packets_built % 10 == 0:
            packet[-1] ^= 0xFF  # checksum invalido: el parser debe descartarla
        return bytes(packet)

    def _raw_packet(self, t: float) -> bytes:
        value = self._raw_sample(t)
        hi, lo = divmod(value & 0xFFFF, 256)
        return self._emit(bytes([Code.RAW_VALUE, 0x02, hi, lo]))

    def _raw_sample(self, t: float) -> int:
        """EEG sintetico: alpha y beta sobre ruido rosa aproximado."""
        alpha = math.sin(2 * math.pi * 10.0 * t)
        beta = 0.35 * math.sin(2 * math.pi * 20.0 * t + 1.1)
        drift = 0.2 * math.sin(2 * math.pi * 0.3 * t)
        noise = self._random.gauss(0.0, 0.25)
        sample = RAW_AMPLITUDE * (alpha + beta + drift + noise) / 2.0
        return max(-2048, min(2047, int(sample)))

    def _esense_packet(self, elapsed: float) -> bytes:
        poor = self._poor_signal(elapsed)
        payload = bytes([Code.POOR_SIGNAL, poor])

        # La diadema real no emite eSense util mientras no hay contacto.
        if poor <= 50:
            attention = self._bounded(60, 18)
            meditation = self._bounded(55, 18)
            payload += bytes([Code.ATTENTION, attention])
            payload += bytes([Code.MEDITATION, meditation])
        return self._emit(payload)

    def _poor_signal(self, elapsed: float) -> int:
        if self.scenario is Scenario.BAD_CONTACT:
            return self._random.choice([55, 80, 110, 200])
        if elapsed < self.contact_delay_s:
            return 200  # electrodo aun sin tocar piel
        return self._random.choice([0, 0, 0, 25])

    def _bands_packet(self) -> bytes:
        raw = b"".join(
            self._random.randint(1_000, 900_000).to_bytes(3, "big") for _ in BAND_NAMES
        )
        return self._emit(bytes([Code.ASIC_EEG_POWER, len(raw)]) + raw)

    def _bounded(self, center: int, spread: int) -> int:
        return max(0, min(100, int(self._random.gauss(center, spread))))
