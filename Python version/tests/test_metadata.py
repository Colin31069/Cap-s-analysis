from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skin_analysis.metadata import load_experiment_metadata, metadata_file_path, save_experiment_metadata
from skin_analysis.models import CurveSplit, DropTimeOverride, ExcludedSample, ExperimentMetadata, MedicineEntry


class MetadataTests(unittest.TestCase):
    def test_missing_metadata_file_returns_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(metadata.medicine_count, 1)
            self.assertEqual(len(metadata.medicines), 1)
            self.assertEqual(metadata.medicines[0], MedicineEntry(name="", dose=""))
            self.assertEqual(metadata.excluded_samples, [])
            self.assertEqual(metadata.curve_splits, [])
            self.assertEqual(metadata.drop_time_overrides, [])

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
                curve_splits=[
                    CurveSplit(file_name="1.xlsx", split_index=4100, split_time_sec=410.0),
                ],
                drop_time_overrides=[
                    DropTimeOverride(file_name="2.xlsx", segment="pbs", drop_time_sec=44.2),
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
            self.assertEqual(metadata.curve_splits, [])
            self.assertEqual(metadata.drop_time_overrides, [])

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
            self.assertEqual(metadata.curve_splits, [])
            self.assertEqual(metadata.drop_time_overrides, [])

    def test_metadata_with_curve_splits_loads_split_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "lanolin", "dose": "1%"}],
  "curve_splits": [
    {
      "file_name": "../1.xlsx",
      "split_index": 4100,
      "split_time_sec": 410.0,
      "left_label": "lanolin_reaction_curve",
      "right_label": "pbs_response_curve"
    }
  ]
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(
                metadata.curve_splits,
                [CurveSplit(file_name="1.xlsx", split_index=4100, split_time_sec=410.0)],
            )

    def test_metadata_with_drop_time_overrides_loads_segment_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(metadata_file_path(tmp_dir)).write_text(
                """
{
  "medicine_count": 1,
  "medicines": [{"name": "lanolin", "dose": "1%"}],
  "drop_time_overrides": [
    {"file_name": "../2.xlsx", "segment": "pbs", "drop_time_sec": 44.2},
    {"file_name": "2.xlsx", "segment": "pbs", "drop_time_sec": 45.0},
    {"file_name": "2.xlsx", "segment": "lanolin", "drop_time_sec": 3.1}
  ]
}
""",
                encoding="utf-8",
            )

            metadata, warning = load_experiment_metadata(tmp_dir)

            self.assertIsNone(warning)
            self.assertEqual(
                metadata.drop_time_overrides,
                [
                    DropTimeOverride(file_name="2.xlsx", segment="pbs", drop_time_sec=44.2),
                    DropTimeOverride(file_name="2.xlsx", segment="lanolin", drop_time_sec=3.1),
                ],
            )

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


if __name__ == "__main__":
    unittest.main()
