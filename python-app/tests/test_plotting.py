from __future__ import annotations

import unittest

import numpy as np

from skin_analysis.models import ExperimentMetadata, MedicineEntry, PlotSettings, ProcessedSignal
from skin_analysis.plotting import (
    build_legend_label,
    build_plot_item,
    build_plot_title,
    display_mode_to_y_unit,
    transform_signal_for_display,
)


def make_settings(**overrides) -> PlotSettings:
    defaults = dict(
        experiment_name="TrialA",
        target_dir="/tmp",
        all_files=["1.xlsx"],
        metadata=ExperimentMetadata(
            medicine_count=2,
            medicines=[
                MedicineEntry(name="lanolin", dose="1% 5mL"),
                MedicineEntry(name="plastik 70", dose="1.5uL"),
            ],
        ),
        is_overlay=False,
        display_mode="Norm",
        use_group_color=True,
        show_drop_lines=True,
        leg_style="Detailed",
        show_base=True,
        show_delta=False,
        baseline_duration_sec=20.0,
        drug_apply_time_sec=25.0,
        drug_apply_tolerance_sec=5.0,
        baseline_warning_threshold_pct=2.0,
    )
    defaults.update(overrides)
    return PlotSettings(**defaults)


def make_signal(**overrides) -> ProcessedSignal:
    defaults = dict(
        time_sec=np.array([0.0, 0.1, 0.2, 0.3], dtype=float),
        capacitance=np.array([10.0, 12.0, 14.0, 16.0], dtype=float),
        drop_time=0.2,
        delta_capacitance=2.5,
        initial_avg=10.0,
        effective_baseline_points=4,
        effective_baseline_duration_sec=0.4,
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


class PlottingTests(unittest.TestCase):
    def test_simple_legend_uses_sample_name_only(self) -> None:
        settings = make_settings(leg_style="Simple")
        label = build_legend_label("3", settings, 10.0, "Δ:2.50pF", "ok")
        self.assertEqual(label, "N 3")

    def test_detailed_legend_includes_enabled_metadata(self) -> None:
        settings = make_settings(show_delta=True)
        label = build_legend_label("3", settings, 10.0, "Δ:2.50pF", "ok")
        self.assertEqual(label, "N 3 (Base:10.00 pF, Δ:2.50pF)")

    def test_legend_suffix_marks_warning_files(self) -> None:
        settings = make_settings(leg_style="Simple")
        label = build_legend_label("3", settings, 10.0, "Δ:2.50pF", "warning")
        self.assertEqual(label, "N 3 [注意]")

    def test_legend_suffix_marks_inaccurate_files(self) -> None:
        settings = make_settings(show_delta=True)
        label = build_legend_label("3", settings, 10.0, "Δ:2.50pF", "inaccurate")
        self.assertEqual(label, "N 3 [不準確] (Base:10.00 pF, Δ:2.50pF)")

    def test_build_plot_title_includes_medicine_metadata(self) -> None:
        title = build_plot_title("TrialA", make_settings().metadata)
        self.assertEqual(title, "TrialA | lanolin: 1% 5mL | plastik 70: 1.5uL")

    def test_build_plot_title_skips_blank_entries(self) -> None:
        metadata = ExperimentMetadata(
            medicine_count=2,
            medicines=[
                MedicineEntry(name="lanolin", dose="1% 5mL"),
                MedicineEntry(name="", dose=""),
            ],
        )
        self.assertEqual(build_plot_title("TrialA", metadata), "TrialA | lanolin: 1% 5mL")

    def test_build_plot_title_uses_experiment_name_when_count_is_zero(self) -> None:
        metadata = ExperimentMetadata(medicine_count=0, medicines=[])
        self.assertEqual(build_plot_title("TrialA", metadata), "TrialA")

    def test_transform_signal_for_normalized_mode(self) -> None:
        x_plot, y_plot, delta_str = transform_signal_for_display(make_signal(), "Norm")
        np.testing.assert_allclose(x_plot, np.array([-0.2, -0.1, 0.0, 0.1]))
        np.testing.assert_allclose(y_plot, np.array([100.0, 120.0, 140.0, 160.0]))
        self.assertEqual(delta_str, "Δ:25.00%")

    def test_transform_signal_for_raw_mode(self) -> None:
        x_plot, y_plot, delta_str = transform_signal_for_display(make_signal(), "Raw")
        np.testing.assert_allclose(x_plot, np.array([-0.2, -0.1, 0.0, 0.1]))
        np.testing.assert_allclose(y_plot, np.array([10.0, 12.0, 14.0, 16.0]))
        self.assertEqual(delta_str, "Δ:2.50pF")

    def test_transform_signal_for_baseline_mode(self) -> None:
        x_plot, y_plot, delta_str = transform_signal_for_display(
            make_signal(effective_baseline_points=2, effective_baseline_duration_sec=0.2),
            "Base",
        )
        np.testing.assert_allclose(x_plot, np.array([-0.2, -0.1]))
        np.testing.assert_allclose(y_plot, np.array([10.0, 12.0]))
        self.assertEqual(delta_str, "Δ:2.50pF")

    def test_build_plot_item_places_drop_marker_at_zero(self) -> None:
        item = build_plot_item(make_signal(), "3", make_settings(display_mode="Raw"), "-", None)
        self.assertAlmostEqual(item.drop_time, 0.0)
        self.assertEqual(item.baseline_warning_details, ())
        self.assertEqual(item.timing_warning_details, ())
        self.assertEqual(item.drop_detection_source, "window")

    def test_build_plot_item_exposes_warning_details(self) -> None:
        signal = make_signal(
            effective_baseline_duration_sec=0.2,
            drop_detection_source="fallback_auto",
            timing_warning_details=("Baseline shortened from 20.0s to 10.0s.",),
            baseline_warning_status="inaccurate",
            baseline_tail_offset_pct=2.8,
            baseline_rise_offset_pct=4.2,
            baseline_tail_warning_hit=True,
            baseline_rise_warning_hit=True,
        )
        item = build_plot_item(signal, "3", make_settings(display_mode="Raw"), "-", None)
        self.assertEqual(item.baseline_warning_status, "inaccurate")
        self.assertEqual(
            item.baseline_warning_details,
            ("尾端均值偏移 +2.80%", "連續上升至 +4.20%"),
        )
        self.assertEqual(item.timing_warning_details, ("Baseline shortened from 20.0s to 10.0s.",))
        self.assertEqual(item.drop_detection_source, "fallback_auto")
        self.assertAlmostEqual(item.effective_baseline_duration_sec, 0.2)

    def test_display_mode_to_y_unit(self) -> None:
        self.assertEqual(display_mode_to_y_unit("Norm"), "Normalized (%)")
        self.assertEqual(display_mode_to_y_unit("Raw"), "Raw Capacitance (pF)")
        self.assertEqual(display_mode_to_y_unit("Base"), "Baseline Capacitance (pF)")


if __name__ == "__main__":
    unittest.main()
