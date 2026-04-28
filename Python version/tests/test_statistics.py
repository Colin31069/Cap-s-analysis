from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from skin_analysis.models import ProcessedSignal, StatisticalSample
from skin_analysis.statistics import (
    SCIPY_AVAILABLE,
    analyze_delta_percent_samples,
    collect_delta_percent_samples,
    delta_percent_from_signal,
    statistics_result_to_csv_rows,
    summarize_group,
)


def make_signal(**overrides) -> ProcessedSignal:
    defaults = dict(
        time_sec=np.array([0.0, 0.1, 0.2], dtype=float),
        capacitance=np.array([10.0, 11.0, 12.0], dtype=float),
        drop_time=0.1,
        delta_capacitance=2.0,
        initial_avg=10.0,
        effective_baseline_points=2,
        effective_baseline_duration_sec=0.2,
        baseline_was_auto_shortened=False,
        drop_detection_source="window",
        drop_search_fallback_used=False,
        timing_warning_details=(),
        baseline_warning_status="ok",
        baseline_tail_offset_pct=0.0,
        baseline_rise_offset_pct=0.0,
        baseline_tail_warning_hit=False,
        baseline_rise_warning_hit=False,
    )
    defaults.update(overrides)
    return ProcessedSignal(**defaults)


def make_sample(group: str, value: float, sample_name: str = "1") -> StatisticalSample:
    return StatisticalSample(
        group_name=group,
        sample_name=sample_name,
        delta_percent=value,
        delta_capacitance=value / 10.0,
        baseline=10.0,
        drop_time=20.0,
        baseline_warning_status="ok",
        drop_detection_source="window",
        warnings=(),
    )


class StatisticsTests(unittest.TestCase):
    def test_delta_percent_uses_each_signal_baseline(self) -> None:
        self.assertAlmostEqual(delta_percent_from_signal(make_signal()), 20.0)
        self.assertTrue(math.isnan(delta_percent_from_signal(make_signal(initial_avg=0.0))))

    def test_summarize_group_returns_descriptive_statistics(self) -> None:
        summary = summarize_group("0.1pct", [1.0, 2.0, 3.0])

        self.assertEqual(summary.group_name, "0.1pct")
        self.assertEqual(summary.n, 3)
        self.assertAlmostEqual(summary.mean, 2.0)
        self.assertAlmostEqual(summary.sd, 1.0)
        self.assertAlmostEqual(summary.sem, 1.0 / math.sqrt(3))
        self.assertAlmostEqual(summary.median, 2.0)
        self.assertAlmostEqual(summary.q1, 1.5)
        self.assertAlmostEqual(summary.q3, 2.5)
        self.assertAlmostEqual(summary.iqr, 1.0)

    def test_analyze_delta_percent_samples_builds_one_way_anova_result(self) -> None:
        samples = [
            make_sample("control", 1.0, "c1"),
            make_sample("control", 2.0, "c2"),
            make_sample("control", 3.0, "c3"),
            make_sample("low", 2.0, "l1"),
            make_sample("low", 3.0, "l2"),
            make_sample("low", 4.0, "l3"),
            make_sample("high", 7.0, "h1"),
            make_sample("high", 8.0, "h2"),
            make_sample("high", 9.0, "h3"),
        ]

        result = analyze_delta_percent_samples(samples, root_path="/tmp/root")

        self.assertEqual([summary.group_name for summary in result.group_statistics], ["control", "low", "high"])
        self.assertEqual(result.anova.method, "One-way ANOVA")
        self.assertEqual(result.anova.group_count, 3)
        self.assertEqual(result.anova.sample_count, 9)
        self.assertGreater(result.anova.eta_squared, 0)

        if SCIPY_AVAILABLE:
            self.assertFalse(math.isnan(result.anova.p_value))
        else:
            self.assertTrue(math.isnan(result.anova.p_value))
            self.assertTrue(any("SciPy is not installed" in warning for warning in result.warnings))

    def test_collect_delta_percent_samples_groups_by_folder_and_skips_bad_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            control = root / "0pct"
            treatment = root / "1pct"
            control.mkdir()
            treatment.mkdir()

            pd.DataFrame({"pF - Plot 0": np.concatenate([np.full(50, 10.0), np.full(120, 12.0)])}).to_excel(
                control / "1.xlsx",
                index=False,
            )
            pd.DataFrame({"pF - Plot 0": np.concatenate([np.full(50, 10.0), np.full(120, 15.0)])}).to_excel(
                treatment / "1.xlsx",
                index=False,
            )
            pd.DataFrame({"wrong": [1, 2, 3]}).to_excel(treatment / "bad.xlsx", index=False)

            samples, warnings = collect_delta_percent_samples(
                tmp_dir,
                baseline_duration_sec=5.0,
                drug_apply_time_sec=10.0,
                drug_apply_tolerance_sec=1.0,
            )

        self.assertEqual([sample.group_name for sample in samples], ["0pct", "1pct"])
        self.assertAlmostEqual(samples[0].delta_percent, 20.0)
        self.assertAlmostEqual(samples[1].delta_percent, 50.0)
        self.assertTrue(any("bad.xlsx could not be analyzed" in warning for warning in warnings))

    def test_statistics_result_to_csv_rows_contains_export_sections(self) -> None:
        result = analyze_delta_percent_samples(
            [
                make_sample("control", 1.0, "c1"),
                make_sample("control", 2.0, "c2"),
                make_sample("drug", 3.0, "d1"),
                make_sample("drug", 4.0, "d2"),
            ]
        )

        rows = statistics_result_to_csv_rows(result)
        first_cells = [row[0] for row in rows if row]

        self.assertIn("Descriptive Statistics", first_cells)
        self.assertIn("One-way ANOVA", first_cells)
        self.assertIn("Per-Sample Delta %", first_cells)


if __name__ == "__main__":
    unittest.main()
