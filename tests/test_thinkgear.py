"""Pruebas del parser ThinkGear.

Se ejecutan sin diadema y sin dependencias externas::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.thinkgear import (  # noqa: E402
    BAND_NAMES,
    Code,
    ThinkGearParser,
    build_packet,
    checksum,
    parse_payload,
)


class TestChecksum(unittest.TestCase):
    """El checksum es suma truncada a 8 bits e invertida."""

    def test_known_vector(self):
        # sum = 0x04 + 0x2A = 0x2E; ~0x2E & 0xFF = 0xD1
        self.assertEqual(checksum(bytes([0x04, 0x2A])), 0xD1)

    def test_empty_payload(self):
        self.assertEqual(checksum(b""), 0xFF)

    def test_covers_whole_payload(self):
        # Cambiar el ultimo byte debe cambiar el checksum. La implementacion
        # anterior sumaba payload[:-1] y por lo tanto lo ignoraba.
        a = checksum(bytes([0x04, 0x10, 0x20]))
        b = checksum(bytes([0x04, 0x10, 0x21]))
        self.assertNotEqual(a, b)

    def test_always_one_byte(self):
        for payload in (b"\x00", b"\xff" * 50, bytes(range(100))):
            self.assertTrue(0 <= checksum(payload) <= 0xFF)


class TestScalarCodes(unittest.TestCase):
    """Codigos de un solo byte de valor."""

    def _one(self, payload: bytes):
        events = ThinkGearParser().feed(build_packet(payload))
        self.assertEqual(len(events), 1)
        return events[0]

    def test_attention(self):
        event = self._one(bytes([Code.ATTENTION, 73]))
        self.assertEqual(event.code, Code.ATTENTION)
        self.assertEqual(event.value, 73)

    def test_meditation(self):
        self.assertEqual(self._one(bytes([Code.MEDITATION, 12])).value, 12)

    def test_poor_signal_no_contact(self):
        # 200 es el valor que reporta la diadema cuando no hay contacto.
        self.assertEqual(self._one(bytes([Code.POOR_SIGNAL, 200])).value, 200)

    def test_several_rows_in_one_packet(self):
        payload = bytes([Code.POOR_SIGNAL, 0, Code.ATTENTION, 60,
                         Code.MEDITATION, 40])
        events = ThinkGearParser().feed(build_packet(payload))
        self.assertEqual(
            [(e.code, e.value) for e in events],
            [(Code.POOR_SIGNAL, 0), (Code.ATTENTION, 60), (Code.MEDITATION, 40)],
        )


class TestRawValue(unittest.TestCase):
    """La senal cruda es un entero con signo de 16 bits big-endian."""

    def _raw(self, hi: int, lo: int) -> int:
        payload = bytes([Code.RAW_VALUE, 0x02, hi, lo])
        events = ThinkGearParser().feed(build_packet(payload))
        self.assertEqual(len(events), 1)
        return events[0].value

    def test_positive(self):
        self.assertEqual(self._raw(0x01, 0x00), 256)

    def test_zero(self):
        self.assertEqual(self._raw(0x00, 0x00), 0)

    def test_negative(self):
        # 0xFFFF con signo es -1; la implementacion anterior restaba 65536 a
        # mano y aqui se delega a int.from_bytes.
        self.assertEqual(self._raw(0xFF, 0xFF), -1)

    def test_most_negative(self):
        self.assertEqual(self._raw(0x80, 0x00), -32768)

    def test_most_positive(self):
        self.assertEqual(self._raw(0x7F, 0xFF), 32767)


class TestBandPowers(unittest.TestCase):
    """Las ocho bandas son enteros de 3 bytes big-endian, base 256."""

    def _bands(self, values):
        raw = b"".join(v.to_bytes(3, "big") for v in values)
        payload = bytes([Code.ASIC_EEG_POWER, 24]) + raw
        events = ThinkGearParser().feed(build_packet(payload))
        self.assertEqual(len(events), 1)
        return events[0].value

    def test_all_bands_present_and_ordered(self):
        bands = self._bands(list(range(1, 9)))
        self.assertEqual(tuple(bands.keys()), BAND_NAMES)
        self.assertEqual(list(bands.values()), list(range(1, 9)))

    def test_base_256_not_255(self):
        # Bytes 01 00 00 valen 65536 en base 256. La implementacion anterior
        # calculaba v0*255*255 + v1*255 + v2 y devolvia 65025.
        bands = self._bands([0x010000] + [0] * 7)
        self.assertEqual(bands["delta"], 65536)
        self.assertNotEqual(bands["delta"], 65025)

    def test_max_value(self):
        bands = self._bands([0xFFFFFF] + [0] * 7)
        self.assertEqual(bands["delta"], 16777215)


class TestChecksumRejection(unittest.TestCase):
    """Una trama corrupta se descarta entera."""

    def test_bad_checksum_yields_nothing(self):
        packet = bytearray(build_packet(bytes([Code.ATTENTION, 50])))
        packet[-1] ^= 0xFF  # corromper el checksum

        parser = ThinkGearParser()
        self.assertEqual(parser.feed(bytes(packet)), [])
        self.assertEqual(parser.packets_bad_checksum, 1)
        self.assertEqual(parser.packets_ok, 0)

    def test_corrupt_payload_is_detected(self):
        packet = bytearray(build_packet(bytes([Code.ATTENTION, 50])))
        packet[4] = 99  # cambiar el valor sin recalcular el checksum

        parser = ThinkGearParser()
        self.assertEqual(parser.feed(bytes(packet)), [])
        self.assertEqual(parser.packets_bad_checksum, 1)

    def test_good_packet_after_bad_one(self):
        bad = bytearray(build_packet(bytes([Code.ATTENTION, 50])))
        bad[-1] ^= 0xFF
        good = build_packet(bytes([Code.ATTENTION, 77]))

        parser = ThinkGearParser()
        events = parser.feed(bytes(bad) + good)
        self.assertEqual([e.value for e in events], [77])
        self.assertEqual(parser.packets_ok, 1)
        self.assertEqual(parser.packets_bad_checksum, 1)


class TestExtendedCodes(unittest.TestCase):
    """El manejo de 0x55 debe terminar siempre."""

    def test_excode_does_not_hang(self):
        # La implementacion anterior entraba en bucle infinito aqui porque
        # reasignaba `code` sin recalcular `code_char`.
        payload = bytes([0x55, 0x55, Code.ATTENTION, 55])
        events = parse_payload(payload)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].extended, 2)
        self.assertEqual(events[0].value, 55)

    def test_payload_of_only_excodes_terminates(self):
        self.assertEqual(parse_payload(bytes([0x55] * 40)), [])

    def test_excode_at_end_terminates(self):
        events = parse_payload(bytes([Code.ATTENTION, 10, 0x55]))
        self.assertEqual([e.value for e in events], [10])


class TestStreamRobustness(unittest.TestCase):
    """Comportamiento frente a un flujo real, sucio y fragmentado."""

    def test_byte_by_byte(self):
        packet = build_packet(bytes([Code.ATTENTION, 88]))
        parser = ThinkGearParser()

        events = []
        for byte in packet:
            events.extend(parser.feed(bytes([byte])))

        self.assertEqual([e.value for e in events], [88])

    def test_garbage_before_sync_is_discarded(self):
        parser = ThinkGearParser()
        events = parser.feed(b"\x01\x02\x03" + build_packet(bytes([Code.ATTENTION, 5])))
        self.assertEqual([e.value for e in events], [5])
        self.assertEqual(parser.bytes_discarded, 3)

    def test_split_sync_pair(self):
        packet = build_packet(bytes([Code.MEDITATION, 31]))
        parser = ThinkGearParser()

        self.assertEqual(parser.feed(b"\x00\xaa"), [])
        events = parser.feed(packet[1:])
        self.assertEqual([e.value for e in events], [31])

    def test_impossible_length_resyncs(self):
        # 0xAA en posicion de longitud obliga a resincronizar.
        noise = bytes([0xAA, 0xAA, 0xAA])
        parser = ThinkGearParser()
        events = parser.feed(noise + build_packet(bytes([Code.ATTENTION, 9])))
        self.assertEqual([e.value for e in events], [9])

    def test_truncated_packet_waits(self):
        packet = build_packet(bytes([Code.ATTENTION, 44]))
        parser = ThinkGearParser()

        self.assertEqual(parser.feed(packet[:-1]), [])
        self.assertGreater(parser.pending_bytes, 0)

        events = parser.feed(packet[-1:])
        self.assertEqual([e.value for e in events], [44])

    def test_truncated_row_does_not_raise(self):
        # Payload que promete 2 bytes de valor y solo trae 1.
        payload = bytes([Code.RAW_VALUE, 0x02, 0x01])
        self.assertEqual(parse_payload(payload), [])

    def test_long_dirty_stream(self):
        parser = ThinkGearParser()
        stream = bytearray()
        expected = []

        for i in range(200):
            stream += bytes([i % 251])  # ruido entre tramas
            value = i % 101
            stream += build_packet(bytes([Code.ATTENTION, value]))
            expected.append(value)

        events = parser.feed(bytes(stream))
        self.assertEqual([e.value for e in events], expected)
        self.assertEqual(parser.packets_ok, 200)
        self.assertEqual(parser.packets_bad_checksum, 0)


class TestPacketLimits(unittest.TestCase):
    """Limites del protocolo."""

    def test_max_payload_is_accepted(self):
        # No existe relleno en ThinkGear: todo byte del payload se interpreta.
        # Se llena con filas validas de dos bytes hasta rozar el limite.
        rows = 84
        payload = bytes([Code.ATTENTION, 50]) * rows
        self.assertEqual(len(payload), 168)

        parser = ThinkGearParser()
        events = parser.feed(build_packet(payload))
        self.assertEqual(len(events), rows)
        self.assertEqual(parser.packets_ok, 1)

    def test_payload_at_exact_limit(self):
        payload = bytes([Code.ATTENTION, 50]) * 84 + bytes([Code.BLINK])
        self.assertEqual(len(payload), 169)

        parser = ThinkGearParser()
        parser.feed(build_packet(payload))
        self.assertEqual(parser.packets_ok, 1)

    def test_oversized_payload_rejected_at_build(self):
        with self.assertRaises(ValueError):
            build_packet(bytes(170))


if __name__ == "__main__":
    unittest.main(verbosity=2)
