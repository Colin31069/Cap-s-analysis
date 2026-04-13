from __future__ import annotations

import unittest

import numpy as np

from skin_analysis.analysis import analyze_signal
from skin_analysis.config import DT_SEC, INITIAL_BASELINE_POINTS


class AnalyzeSignalTests(unittest.TestCase):
    def test_baseline_uses_configured_window_for_long_signal(self) -> None:
        baseline = np.full(INITIAL_BASELINE_POINTS, 10.0)
        tail = np.full(120, 13.0)
        signal = analyze_signal(np.concatenate([baseline, tail]))

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertAlmostEqual(signal.initial_avg, 10.0)
        self.assertAlmostEqual(signal.drop_time, INITIAL_BASELINE_POINTS * DT_SEC)

    def test_short_signal_uses_full_length_as_baseline(self) -> None:
        samples = np.array([2.0, 4.0, 6.0, 8.0], dtype=float)
        signal = analyze_signal(samples)

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertAlmostEqual(signal.initial_avg, float(np.mean(samples)))
        self.assertTrue(np.isnan(signal.delta_capacitance))
        self.assertAlmostEqual(signal.drop_time, len(samples) * DT_SEC)

    def test_threshold_crossing_detection_uses_first_crossing_after_baseline(self) -> None:
        baseline = np.full(INITIAL_BASELINE_POINTS, 5.0)
        after = np.array([5.0, 5.0, 5.0, 8.5, 9.0], dtype=float)
        signal = analyze_signal(np.concatenate([baseline, after]))

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertAlmostEqual(signal.drop_time, (INITIAL_BASELINE_POINTS + 3) * DT_SEC)

    def test_no_crossing_falls_back_to_baseline_boundary(self) -> None:
        samples = np.full(INITIAL_BASELINE_POINTS + 10, 7.0)
        signal = analyze_signal(samples)

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertAlmostEqual(signal.drop_time, INITIAL_BASELINE_POINTS * DT_SEC)

    def test_delta_uses_last_hundred_points_when_available(self) -> None:
        baseline = np.full(INITIAL_BASELINE_POINTS, 10.0)
        middle = np.full(50, 11.0)
        tail = np.full(100, 14.0)
        signal = analyze_signal(np.concatenate([baseline, middle, tail]))

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertAlmostEqual(signal.delta_capacitance, 4.0)


if __name__ == "__main__":
    unittest.main()
