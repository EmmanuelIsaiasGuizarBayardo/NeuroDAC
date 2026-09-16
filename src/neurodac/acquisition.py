"""Servicio de adquisicion de NeuroDAC.

Una sola pieza es duena del puerto. Las paginas de Dash no abren nada: piden
una sesion al registro y leen de ella. Eso es lo que evita que el puerto quede
tomado al navegar entre paginas.

El hilo lector empuja cada muestra a la cola en cuanto llega, en lugar de que
un segundo hilo encueste un atributo. Con eso el muestreo es exacto y
desaparece un hilo por sesion.

La fuente de bytes esta detras de `Source`, de modo que la diadema real y la
simulada comparten todo lo que viene despues, incluido el parser.
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .thinkgear import BAND_NAMES, Code, Event, ThinkGearParser

#: La terminal es el instrumento de diagnostico durante una demostracion, asi
#: que todo lo que le pase al enlace se registra en lugar de silenciarse.
logger = logging.getLogger(__name__)

__all__ = [
    "SIGNAL_TYPES",
    "Quality",
    "SerialSource",
    "Session",
    "SessionRegistry",
    "SignalState",
    "Source",
    "registry",
    "validate_signal_type",
]

BAUDRATE = 115200

#: Sin paquetes nuevos durante este tiempo, la senal se considera perdida.
DATA_TIMEOUT_S = 3.0

#: Margen para que el algoritmo eSense establezca su linea base adaptativa.
#: Antes de esto, `attention` y `meditation` no son confiables.
WARMUP_S = 10.0

#: `poor_signal` va de 0 (contacto perfecto) a 200 (sin contacto).
NO_CONTACT = 200
POOR_CONTACT_THRESHOLD = 50

RATE_WINDOW_S = 1.0
BUFFER_MAXLEN = 4096

_SCALAR_CODES: dict[str, Code] = {
    "raw": Code.RAW_VALUE,
    "attention": Code.ATTENTION,
    "meditation": Code.MEDITATION,
    "blink": Code.BLINK,
}

#: Tipos de senal que una sesion puede transmitir.
SIGNAL_TYPES: tuple[str, ...] = tuple(_SCALAR_CODES) + BAND_NAMES


def validate_signal_type(signal_type: str) -> None:
    """Valida el nombre de una senal.

    Raises
    ------
    ValueError
        Si el nombre no corresponde a ninguna senal conocida.
    """
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(
            f"Tipo de senal invalido: {signal_type!r}. "
            f"Validos: {', '.join(SIGNAL_TYPES)}"
        )


class SignalState(StrEnum):
    """Estado del enlace con la diadema, tal como lo ve el operador."""

    DISCONNECTED = "desconectada"
    NO_DATA = "sin_datos"
    NO_CONTACT = "sin_contacto"
    POOR_CONTACT = "contacto_pobre"
    CALIBRATING = "calibrando"
    READY = "lista"


@dataclass(frozen=True)
class Quality:
    """Fotografia del enlace en un instante.

    Attributes
    ----------
    state : SignalState
        Estado agregado; es lo unico que los juegos necesitan consultar.
    poor_signal : int or None
        Ultimo valor reportado por la diadema, `None` si aun no llega ninguno.
    packet_rate_hz : float
        Tramas validas por segundo en la ultima ventana.
    seconds_since_last_packet : float or None
        Antiguedad de la ultima trama valida.
    calibration_progress : float
        Avance del calentamiento de eSense, de 0.0 a 1.0.
    packets_ok, packets_bad_checksum, bytes_discarded : int
        Contadores acumulados del parser.
    error : str or None
        Ultimo error del hilo lector, si lo hubo.
    """

    state: SignalState
    poor_signal: int | None
    packet_rate_hz: float
    seconds_since_last_packet: float | None
    calibration_progress: float
    packets_ok: int
    packets_bad_checksum: int
    bytes_discarded: int
    error: str | None

    @property
    def is_ready(self) -> bool:
        """True cuando la senal sirve para controlar un juego."""
        return self.state is SignalState.READY


class Source(Protocol):
    """Origen de bytes en formato ThinkGear."""

    name: str

    def open(self) -> None:
        """Abre el recurso. Lanza excepcion si no es posible."""

    def read(self, timeout: float) -> bytes:
        """Devuelve los bytes disponibles, esperando a lo sumo `timeout`."""

    def close(self) -> None:
        """Libera el recurso. Debe tolerar llamadas repetidas."""


class SerialSource:
    """Diadema real sobre un puerto serial.

    Parameters
    ----------
    port : str
        Puerto COM en Windows o ruta de dispositivo en Unix.
    handshake : bool, optional
        Repite la secuencia de inicializacion de la implementacion anterior.
        Esa secuencia apunta al dongle USB de NeuroSky; sobre Bluetooth SPP
        probablemente sea inocua. Se conserva encendida porque es el
        comportamiento que hoy funciona, y va protegida para que su fallo no
        tumbe la conexion.
    """

    def __init__(self, port: str, *, handshake: bool = True) -> None:
        self.name = port
        self.port = port
        self.handshake = handshake
        self._serial = None

    def open(self) -> None:
        import serial  # Import diferido: las pruebas corren sin pyserial.

        self._serial = serial.Serial(self.port, BAUDRATE, timeout=0.1)
        if self.handshake:
            self._try_handshake()

    def _try_handshake(self) -> None:
        try:
            self._serial.write(b"\xc1")  # DISCONNECT
            settings = self._serial.getSettingsDict()
            for _ in range(2):
                settings["rtscts"] = not settings["rtscts"]
                self._serial.applySettingsDict(settings)
        except Exception as exc:  # noqa: BLE001
            # Un puerto SPP puede no soportar control de flujo por hardware.
            # No es fatal, pero conviene verlo en la terminal.
            logger.warning("Handshake omitido en %s: %s", self.port, exc)

    def read(self, timeout: float) -> bytes:
        if self._serial is None:
            return b""
        pending = self._serial.in_waiting
        if pending:
            return self._serial.read(pending)
        # `timeout` del puerto hace la espera; leer 1 byte evita girar en vacio.
        return self._serial.read(1)

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None


class Session:
    """Adquisicion sobre una fuente, con estado observable.

    Una sesion transmite un tipo de senal a la vez, pero siempre rastrea
    `poor_signal` y el ultimo valor de cada senal, porque el operador los
    necesita aunque la pagina este graficando otra cosa.
    """

    def __init__(self, source: Source, signal_type: str = "raw") -> None:
        validate_signal_type(signal_type)
        self.source = source
        self._signal_type = signal_type

        self._parser = ThinkGearParser()
        self._samples: deque[float] = deque(maxlen=BUFFER_MAXLEN)
        self._latest: dict[str, float] = {}
        self._packet_times: deque[float] = deque(maxlen=1024)

        self._poor_signal: int | None = None
        self._good_contact_since: float | None = None
        self._last_packet_at: float | None = None
        self._error: str | None = None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------------------------------------------------------------- ciclo

    def start(self) -> None:
        """Abre la fuente y lanza el hilo lector."""
        if self.is_running:
            return
        self.source.open()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"neurodac-{self.source.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Detiene el hilo y cierra la fuente. Tolera llamadas repetidas."""
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self.source.close()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---------------------------------------------------------------- datos

    @property
    def signal_type(self) -> str:
        return self._signal_type

    def set_signal_type(self, signal_type: str) -> None:
        """Cambia la senal transmitida y descarta lo acumulado de la anterior."""
        validate_signal_type(signal_type)
        with self._lock:
            if signal_type == self._signal_type:
                return
            self._signal_type = signal_type
            self._samples.clear()

    def drain(self) -> list[float]:
        """Extrae y devuelve las muestras acumuladas desde la llamada previa."""
        out: list[float] = []
        while True:
            try:
                out.append(self._samples.popleft())
            except IndexError:
                return out

    def latest(self, signal_type: str | None = None) -> float | None:
        """Ultimo valor conocido de una senal, sin consumirlo."""
        key = signal_type or self._signal_type
        with self._lock:
            return self._latest.get(key)

    # -------------------------------------------------------------- calidad

    @property
    def quality(self) -> Quality:
        """Estado actual del enlace."""
        now = time.monotonic()
        with self._lock:
            poor = self._poor_signal
            last = self._last_packet_at
            good_since = self._good_contact_since
            error = self._error
            rate = sum(1 for t in self._packet_times if now - t <= RATE_WINDOW_S)

        age = None if last is None else now - last
        progress = 0.0
        if good_since is not None:
            progress = min(1.0, (now - good_since) / WARMUP_S)

        state = self._resolve_state(age, poor, progress)
        return Quality(
            state=state,
            poor_signal=poor,
            packet_rate_hz=rate / RATE_WINDOW_S,
            seconds_since_last_packet=age,
            calibration_progress=progress,
            packets_ok=self._parser.packets_ok,
            packets_bad_checksum=self._parser.packets_bad_checksum,
            bytes_discarded=self._parser.bytes_discarded,
            error=error,
        )

    def _resolve_state(
        self, age: float | None, poor: int | None, progress: float
    ) -> SignalState:
        """Decide el estado agregado a partir de las senales crudas."""
        if not self.is_running:
            return SignalState.DISCONNECTED
        # Sin trama valida reciente el enlace esta caido, aunque el puerto siga
        # abierto. Es el caso que antes dejaba el indicador en verde mintiendo.
        if age is None or age > DATA_TIMEOUT_S:
            return SignalState.NO_DATA
        if poor is None:
            return SignalState.NO_DATA
        if poor >= NO_CONTACT:
            return SignalState.NO_CONTACT
        if poor > POOR_CONTACT_THRESHOLD:
            return SignalState.POOR_CONTACT
        if progress < 1.0:
            return SignalState.CALIBRATING
        return SignalState.READY

    # ----------------------------------------------------------------- hilo

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                data = self.source.read(timeout=0.1)
            except Exception as exc:  # noqa: BLE001
                # El hilo muere, pero deja rastro: es lo que le dice al
                # operador que hay que reiniciar en vez de seguir esperando.
                logger.error("Lectura interrumpida en %s: %s", self.source.name, exc)
                with self._lock:
                    self._error = f"{type(exc).__name__}: {exc}"
                return
            if not data:
                continue
            for event in self._parser.feed(data):
                self._handle(event)

    def _handle(self, event: Event) -> None:
        """Encamina un evento decodificado hacia el estado de la sesion."""
        now = time.monotonic()

        with self._lock:
            previous = self._last_packet_at
            self._last_packet_at = now
            self._packet_times.append(now)

            # Un corte de datos invalida la linea base de eSense igual que
            # perder el contacto: al volver hay que calibrar otra vez.
            if previous is not None and now - previous > DATA_TIMEOUT_S:
                self._good_contact_since = None

            if event.code == Code.POOR_SIGNAL:
                self._on_poor_signal(int(event.value), now)
                return

            if event.code == Code.ASIC_EEG_POWER and isinstance(event.value, dict):
                self._latest.update(event.value)
                if self._signal_type in event.value:
                    self._samples.append(event.value[self._signal_type])
                return

            name = _NAME_BY_CODE.get(event.code)
            if name is None or not isinstance(event.value, int):
                return
            self._latest[name] = event.value
            if name == self._signal_type:
                self._samples.append(event.value)

    def _on_poor_signal(self, value: int, now: float) -> None:
        """Actualiza el contacto y reinicia el calentamiento si se pierde."""
        self._poor_signal = value
        self._latest["poor_signal"] = value
        if value > POOR_CONTACT_THRESHOLD:
            # Perder contacto invalida la linea base de eSense: hay que
            # volver a calibrar desde cero cuando el contacto regrese.
            self._good_contact_since = None
        elif self._good_contact_since is None:
            self._good_contact_since = now


_NAME_BY_CODE: dict[int, str] = {code: name for name, code in _SCALAR_CODES.items()}


class SessionRegistry:
    """Sesiones indexadas por fuente, una por puerto.

    Que el registro sea por puerto es lo que resuelve el bloqueo: dos paginas
    que pidan el mismo COM reciben la misma sesion en lugar de intentar abrir
    el puerto dos veces.

    El indexado por clave deja lista la segunda diadema: seria otra entrada
    del diccionario, no otra variable global.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def acquire(self, source: Source, signal_type: str = "raw") -> Session:
        """Devuelve la sesion de esa fuente, creandola e iniciandola si falta.

        Si ya existe, se reutiliza y solo se ajusta el tipo de senal.
        """
        validate_signal_type(signal_type)
        with self._lock:
            session = self._sessions.get(source.name)
            if session is not None and session.is_running:
                session.set_signal_type(signal_type)
                return session

            if session is not None:
                session.stop()

            session = Session(source, signal_type)
            self._sessions[source.name] = session

        try:
            session.start()
        except Exception:
            with self._lock:
                self._sessions.pop(source.name, None)
            raise
        return session

    def get(self, name: str) -> Session | None:
        with self._lock:
            return self._sessions.get(name)

    def stop(self, name: str) -> bool:
        """Detiene y olvida una sesion. True si existia."""
        with self._lock:
            session = self._sessions.pop(name, None)
        if session is None:
            return False
        session.stop()
        return True

    def stop_all(self) -> None:
        """Detiene todas las sesiones y libera todos los puertos."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.stop()

    @property
    def names(self) -> list[str]:
        with self._lock:
            return list(self._sessions)


#: Registro unico del proceso. Las paginas lo importan y nunca crean el suyo.
registry = SessionRegistry()

# Libera los puertos si el proceso termina sin pasar por el boton de Detener.
atexit.register(registry.stop_all)
