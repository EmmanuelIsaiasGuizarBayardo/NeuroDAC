"""Parser del protocolo serial ThinkGear (NeuroSky MindWave Mobile).

Convierte un flujo de bytes en eventos tipados. Es deliberadamente puro: no
abre puertos, no lanza hilos y no depende de nada fuera de la biblioteca
estandar, de modo que puede probarse sin la diadema conectada.

Estructura de una trama::

    [0xAA] [0xAA] [PLENGTH] [PAYLOAD ... PLENGTH bytes] [CHECKSUM]

El payload contiene una o mas filas de datos::

    [0x55]* [CODE] ([VLENGTH]) [VALUE ...]

Los codigos menores a 0x80 llevan un solo byte de valor; los mayores o iguales
llevan un byte de longitud seguido de esa cantidad de bytes.

Referencia: NeuroSky, "ThinkGear Serial Stream Guide".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

__all__ = [
    "Code",
    "Event",
    "ThinkGearParser",
    "BAND_NAMES",
    "checksum",
    "build_packet",
    "parse_payload",
]

SYNC = 0xAA
EXCODE = 0x55

# 0xAA (170) nunca es una longitud valida: en esa posicion significa que hay
# que resincronizar, porque se esta leyendo el SYNC de la siguiente trama.
MAX_PAYLOAD_LENGTH = 169

BAND_NAMES = (
    "delta", "theta",
    "low-alpha", "high-alpha",
    "low-beta", "high-beta",
    "low-gamma", "mid-gamma",
)


class Code(IntEnum):
    """Codigos de dato del protocolo ThinkGear."""

    POOR_SIGNAL = 0x02
    ATTENTION = 0x04
    MEDITATION = 0x05
    BLINK = 0x16
    RAW_VALUE = 0x80
    ASIC_EEG_POWER = 0x83


@dataclass(frozen=True)
class Event:
    """Un dato decodificado del flujo.

    Attributes
    ----------
    code : int
        Codigo ThinkGear. Puede compararse contra `Code`.
    value : int or dict or bytes
        Entero para escalares, diccionario de bandas para `ASIC_EEG_POWER`,
        y bytes crudos para codigos desconocidos.
    extended : int
        Nivel de codigo extendido, es decir cuantos 0x55 precedieron al codigo.
    """

    code: int
    value: object
    extended: int = 0


def checksum(payload: bytes) -> int:
    """Calcula el checksum ThinkGear de un payload.

    Parameters
    ----------
    payload : bytes
        Payload completo, sin los bytes de sincronizacion ni la longitud.

    Returns
    -------
    int
        Suma de los bytes, truncada a 8 bits e invertida.
    """
    return (~(sum(payload) & 0xFF)) & 0xFF


def build_packet(payload: bytes) -> bytes:
    """Arma una trama completa a partir de un payload.

    Se usa en pruebas y en el generador de senal simulada.

    Raises
    ------
    ValueError
        Si el payload excede la longitud maxima del protocolo.
    """
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError(
            f"payload de {len(payload)} bytes; el maximo es {MAX_PAYLOAD_LENGTH}"
        )
    return bytes([SYNC, SYNC, len(payload)]) + payload + bytes([checksum(payload)])


def _decode_value(code: int, raw: bytes) -> object:
    """Traduce el campo de valor segun el codigo."""
    if code == Code.RAW_VALUE and len(raw) >= 2:
        # Entero con signo de 16 bits, big-endian.
        return int.from_bytes(raw[:2], "big", signed=True)

    if code == Code.ASIC_EEG_POWER and len(raw) >= 24:
        # Ocho bandas, cada una entero sin signo de 3 bytes big-endian.
        # Base 256, no 255: es donde fallaba la implementacion anterior.
        return {
            name: int.from_bytes(raw[i * 3:i * 3 + 3], "big")
            for i, name in enumerate(BAND_NAMES)
        }

    return raw


def parse_payload(payload: bytes) -> list[Event]:
    """Decodifica las filas de datos contenidas en un payload.

    Tolera payloads truncados: si una fila queda incompleta se descarta el
    resto en lugar de lanzar una excepcion, porque un payload malformado no
    debe tumbar la adquisicion.
    """
    events: list[Event] = []
    i = 0
    n = len(payload)

    while i < n:
        # Contar codigos extendidos. El avance de `i` es lo que garantiza que
        # este bucle siempre termine.
        extended = 0
        while i < n and payload[i] == EXCODE:
            extended += 1
            i += 1
        if i >= n:
            break

        code = payload[i]
        i += 1

        if code < 0x80:
            if i >= n:
                break
            events.append(Event(code, payload[i], extended))
            i += 1
            continue

        if i >= n:
            break
        vlength = payload[i]
        i += 1
        if i + vlength > n:
            break

        raw = payload[i:i + vlength]
        i += vlength
        events.append(Event(code, _decode_value(code, raw), extended))

    return events


class ThinkGearParser:
    """Maquina de estados incremental sobre el flujo serial.

    Acepta los bytes en trozos de cualquier tamano y solo emite eventos de
    tramas cuyo checksum es correcto. Lleva contadores para que la interfaz
    pueda mostrarle al operador si el enlace esta sano.

    Examples
    --------
    >>> parser = ThinkGearParser()
    >>> parser.feed(build_packet(bytes([0x04, 42])))
    [Event(code=4, value=42, extended=0)]
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.packets_ok = 0
        self.packets_bad_checksum = 0
        self.bytes_discarded = 0

    def feed(self, data: bytes) -> list[Event]:
        """Ingresa bytes y devuelve los eventos completos que se pudieron leer."""
        self._buffer.extend(data)
        events: list[Event] = []
        for payload in self._take_payloads():
            events.extend(parse_payload(payload))
        return events

    def reset(self) -> None:
        """Vacia el buffer sin tocar los contadores."""
        self._buffer.clear()

    @property
    def pending_bytes(self) -> int:
        """Bytes en espera de completar una trama."""
        return len(self._buffer)

    def _take_payloads(self):
        """Extrae del buffer todas las tramas completas y validas."""
        while True:
            if not self._seek_sync():
                return

            if len(self._buffer) < 3:
                return

            plength = self._buffer[2]
            if plength > MAX_PAYLOAD_LENGTH:
                # Longitud imposible: descartar un byte y volver a buscar.
                del self._buffer[:1]
                self.bytes_discarded += 1
                continue

            total = 3 + plength + 1
            if len(self._buffer) < total:
                return

            payload = bytes(self._buffer[3:3 + plength])
            received = self._buffer[3 + plength]
            del self._buffer[:total]

            if checksum(payload) == received:
                self.packets_ok += 1
                yield payload
            else:
                # Trama corrupta: se descarta entera. Procesarla era la causa
                # de que un glitch de Bluetooth llegara hasta el decodificador.
                self.packets_bad_checksum += 1

    def _seek_sync(self) -> bool:
        """Deja el buffer empezando en SYNC SYNC. False si aun no aparece."""
        index = self._buffer.find(b"\xaa\xaa")
        if index < 0:
            # Conservar el ultimo byte: puede ser el primer SYNC de un par
            # que quedo partido entre dos lecturas.
            drop = max(0, len(self._buffer) - 1)
            if drop:
                del self._buffer[:drop]
                self.bytes_discarded += drop
            return False

        if index:
            del self._buffer[:index]
            self.bytes_discarded += index
        return True
