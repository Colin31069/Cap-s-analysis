from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skin_analysis.metadata import load_experiment_metadata, metadata_file_path, save_experiment_metadata
from skin_analysis.models import ExperimentMetadata, MedicineEntry


class MetadataTests(unittest.TestCase):
    def test_missing_metadata_file_returns_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(metadata.medicine_count, 1)
            self.assertEqual(len(metadata.medicines), 1)
            self.assertEqual(metadata.medicines[0], MedicineEntry(name="", dose=""))

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata = ExperimentMetadata(
                medicine_count=2,
                medicines=[
                    MedicineEntry(name="lanolin", dose="1% 5mL"),
                    MedicineEntry(name="plastik 70", dose="1.5uL"),
                ],
            )

            save_experiment_metadata(tmp_dir, metadata)
            loaded, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(loaded, metadata)

    def test_invalid_json_falls_back_to_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text("{not valid json", encoding="utf-8")

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNotNone(warning)
            self.assertEqual(metadata.medicine_count, 1)
            self.assertEqual(metadata.medicines, [MedicineEntry(name="", dose="")])


if __name__ == "__main__":
    unittest.main()
