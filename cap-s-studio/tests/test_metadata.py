from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cap_s.metadata import load_experiment_metadata, metadata_file_path, save_experiment_metadata
from cap_s.models import ExcludedSample, ExperimentMetadata, MedicineEntry


class MetadataTests(unittest.TestCase):
    def test_missing_metadata_file_returns_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(metadata.medicine_count, 1)
            self.assertEqual(len(metadata.medicines), 1)
            self.assertEqual(metadata.medicines[0], MedicineEntry(name="", dose=""))
            self.assertEqual(metadata.excluded_samples, [])

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata = ExperimentMetadata(
                medicine_count=2,
                medicines=[
                    MedicineEntry(name="lanolin", dose="1% 5mL"),
                    MedicineEntry(name="plastik 70", dose="1.5uL"),
                ],
                excluded_samples=[
                    ExcludedSample(file_name="3.xlsx", reason="baseline drift"),
                    ExcludedSample(file_name="5.xlsx", reason="Dixon Q", method="dixon_q"),
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
            self.assertEqual(metadata.excluded_samples, [])

    def test_metadata_without_exclusions_loads_as_empty_exclusion_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "lanolin", "dose": "1%"}]
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(metadata.excluded_samples, [])

    def test_duplicate_excluded_samples_are_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "", "dose": ""}],
  "excluded_samples": [
    {"file_name": "3.xlsx", "reason": ""},
    {"file_name": "3.xlsx", "reason": "baseline drift"},
    {"file_name": "4.xlsx", "reason": "bad contact"}
  ]
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(
                metadata.excluded_samples,
                [
                    ExcludedSample(file_name="3.xlsx", reason="baseline drift"),
                    ExcludedSample(file_name="4.xlsx", reason="bad contact"),
                ],
            )

    def test_excluded_sample_method_is_optional_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "", "dose": ""}],
  "excluded_samples": [
    {"file_name": "2.xlsx", "reason": "old manual reason"},
    {"file_name": "3.xlsx", "reason": "Dixon Q", "method": "dixon_q"}
  ]
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(
                metadata.excluded_samples,
                [
                    ExcludedSample(file_name="2.xlsx", reason="old manual reason"),
                    ExcludedSample(file_name="3.xlsx", reason="Dixon Q", method="dixon_q"),
                ],
            )

    def test_invalid_excluded_samples_falls_back_to_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "", "dose": ""}],
  "excluded_samples": "3.xlsx"
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNotNone(warning)
            self.assertEqual(metadata.medicine_count, 1)
            self.assertEqual(metadata.excluded_samples, [])






    def test_atomic_save_failure_preserves_original_json_and_cleans_temp(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            original = ExperimentMetadata(1, [MedicineEntry("original", "1%")],
                                          [ExcludedSample(file_name="2.xlsx", reason="bad contact")])
            save_experiment_metadata(tmp_dir, original)
            path = Path(metadata_file_path(tmp_dir))
            original_bytes = path.read_bytes()
            new_metadata = ExperimentMetadata(1, [MedicineEntry("changed", "2%")], [])
            with patch("cap_s.metadata.os.replace", side_effect=OSError("simulated replacement failure")):
                with self.assertRaisesRegex(OSError, "simulated replacement failure"):
                    save_experiment_metadata(tmp_dir, new_metadata)
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(list(Path(tmp_dir).glob("*.tmp")), [])



if __name__ == "__main__":
    unittest.main()
