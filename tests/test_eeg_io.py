"""Pruebas de la capa de datos EEG.

No requieren un `.set`: lo que se verifica son las invariantes (microvoltios,
media cero), la ida y vuelta por CSV, y sobre todo que la carga degrade en
lugar de fallar cuando `data/` esta vacia, que es el estado de un clon nuevo.

    uv run pytest tests/test_eeg_io.py -q
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from neurodac.eeg_io import (
    DEFAULT_DEMO_NAME,
    DEFAULT_SAMPLE_RATE,
    Recording,
    find_demo_csv,
    load_demo,
    read_csv,
    remove_dc_offset,
    write_csv,
)


def make_recording(n_channels: int = 3, n_samples: int = 1024) -> Recording:
    """Registro sintetico con offset deliberado en cada canal."""
    rng = np.random.default_rng(0)
    data = rng.normal(0, 50, size=(n_channels, n_samples))
    data += np.arange(1, n_channels + 1)[:, None] * 1000.0
    return Recording(
        channels=tuple(f"Ch{i}" for i in range(n_channels)),
        data=data,
        sample_rate=512.0,
    )


class TestRemoveDcOffset(unittest.TestCase):
    def test_each_channel_is_centered(self):
        centered = remove_dc_offset(make_recording().data)
        np.testing.assert_allclose(centered.mean(axis=1), 0.0, atol=1e-9)

    def test_shape_is_preserved(self):
        data = make_recording().data
        self.assertEqual(remove_dc_offset(data).shape, data.shape)

    def test_variability_is_preserved(self):
        # Restar la media no debe tocar la forma de la senal.
        data = make_recording().data
        np.testing.assert_allclose(
            remove_dc_offset(data).std(axis=1), data.std(axis=1), rtol=1e-9
        )

    def test_input_is_not_mutated(self):
        data = make_recording().data
        before = data.copy()
        remove_dc_offset(data)
        np.testing.assert_array_equal(data, before)

    def test_empty_input(self):
        self.assertEqual(remove_dc_offset(np.empty((0, 0))).size, 0)


class TestRecording(unittest.TestCase):
    def test_derived_properties(self):
        recording = make_recording(4, 1024)
        self.assertEqual(recording.n_channels, 4)
        self.assertEqual(recording.n_samples, 1024)
        self.assertAlmostEqual(recording.duration_s, 2.0)

    def test_index_of_known_and_unknown(self):
        recording = make_recording()
        self.assertEqual(recording.index_of("Ch1"), 1)
        with self.assertRaises(KeyError):
            recording.index_of("Fp1")

    def test_window_returns_expected_span(self):
        recording = make_recording(2, 1024)
        times, data = recording.window(0.5, 1.0)
        self.assertEqual(data.shape, (2, 256))
        self.assertAlmostEqual(times[0], 0.5)

    def test_window_is_clamped_instead_of_failing(self):
        recording = make_recording(2, 1024)
        times, data = recording.window(-5.0, 999.0)
        self.assertEqual(data.shape[1], recording.n_samples)
        self.assertAlmostEqual(times[0], 0.0)

    def test_inverted_window_is_empty(self):
        _, data = make_recording().window(1.0, 0.5)
        self.assertEqual(data.shape[1], 0)

    def test_channel_count_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            Recording(channels=("a", "b"), data=np.zeros((3, 10)), sample_rate=512.0)

    def test_bad_sample_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            Recording(channels=("a",), data=np.zeros((1, 10)), sample_rate=0.0)


class TestCsvRoundTrip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "registro.csv"

    def test_round_trip_preserves_data_within_precision(self):
        original = make_recording(3, 512)
        write_csv(original, self.path)
        restored = read_csv(self.path)

        self.assertEqual(restored.channels, original.channels)
        # Un decimal cuantiza a +-0.05 uV; recentrar tras redondear agrega
        # un corrimiento del orden de 0.002 uV. La cota honesta es 0.06.
        np.testing.assert_allclose(
            restored.data, remove_dc_offset(original.data), atol=0.06
        )

    def test_more_decimals_reduce_the_error(self):
        original = remove_dc_offset(make_recording(2, 256).data)
        recording = Recording(channels=("A", "B"), data=original, sample_rate=512.0)

        errors = []
        for decimals in (0, 1, 2):
            write_csv(recording, self.path, decimals=decimals)
            errors.append(np.abs(read_csv(self.path).data - original).max())

        self.assertTrue(
            errors[0] > errors[1] > errors[2],
            f"el error deberia caer al agregar decimales: {errors}",
        )

    def test_sample_rate_is_inferred_from_timestamps(self):
        write_csv(make_recording(2, 512), self.path)
        self.assertAlmostEqual(read_csv(self.path).sample_rate, 512.0, places=3)

    def test_legacy_timestamp_column_is_recognised(self):
        # La primera version del proyecto escribio la columna asi.
        self.path.write_text(
            "git Timestamp,Raw\n0.0,10\n0.5,20\n1.0,30\n", encoding="utf-8"
        )
        recording = read_csv(self.path)
        self.assertEqual(recording.channels, ("Raw",))
        self.assertAlmostEqual(recording.sample_rate, 2.0)

    def test_csv_without_time_column_uses_default_rate(self):
        self.path.write_text("Fp1,Fp2\n1,2\n3,4\n", encoding="utf-8")
        self.assertEqual(read_csv(self.path).sample_rate, DEFAULT_SAMPLE_RATE)

    def test_column_names_are_stripped(self):
        self.path.write_text(" Timestamp , Fp1 \n0.0,1\n0.5,2\n", encoding="utf-8")
        self.assertEqual(read_csv(self.path).channels, ("Fp1",))

    def test_csv_with_only_time_is_rejected(self):
        self.path.write_text("Timestamp\n0.0\n0.5\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_csv(self.path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_csv(Path(self.dir.name) / "no-existe.csv")


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / "processed").mkdir()

    def test_canonical_name_wins(self):
        (self.root / "processed" / "otro.csv").write_text("Fp1\n1\n", encoding="utf-8")
        canonical = self.root / "processed" / DEFAULT_DEMO_NAME
        canonical.write_text("Fp1\n1\n", encoding="utf-8")
        self.assertEqual(find_demo_csv(self.root), canonical)

    def test_falls_back_to_any_processed_csv(self):
        other = self.root / "processed" / "otro.csv"
        other.write_text("Fp1\n1\n", encoding="utf-8")
        self.assertEqual(find_demo_csv(self.root), other)

    def test_returns_none_when_empty(self):
        self.assertIsNone(find_demo_csv(self.root))

    def test_returns_none_for_missing_directory(self):
        self.assertIsNone(find_demo_csv(self.root / "fantasma"))

    def test_ignores_loose_csv_in_the_data_root(self):
        # data/ no se versiona y acumula archivos sueltos; cargar uno por
        # accidente significa mirar una senal distinta de la que se cree.
        (self.root / "suelto.csv").write_text("Fp1\n1\n", encoding="utf-8")
        self.assertIsNone(find_demo_csv(self.root))

    def test_returns_none_without_a_processed_directory(self):
        import shutil

        shutil.rmtree(self.root / "processed")
        self.assertIsNone(find_demo_csv(self.root))


class TestLoadDemoDegrades(unittest.TestCase):
    """La aplicacion debe arrancar aunque `data/` este vacia."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)

    def test_none_when_there_is_nothing(self):
        (self.root / "processed").mkdir()
        self.assertIsNone(load_demo(self.root))

    def test_none_when_directory_does_not_exist(self):
        self.assertIsNone(load_demo(self.root / "fantasma"))

    def test_none_when_the_csv_is_corrupt(self):
        processed = self.root / "processed"
        processed.mkdir()
        (processed / DEFAULT_DEMO_NAME).write_bytes(b"\x00\x01\x02 basura")
        self.assertIsNone(load_demo(self.root))

    def test_recording_when_the_csv_is_valid(self):
        processed = self.root / "processed"
        processed.mkdir()
        write_csv(make_recording(2, 256), processed / DEFAULT_DEMO_NAME)

        recording = load_demo(self.root)
        self.assertIsNotNone(recording)
        self.assertEqual(recording.n_channels, 2)
        np.testing.assert_allclose(recording.data.mean(axis=1), 0.0, atol=1e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
