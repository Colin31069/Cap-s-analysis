from __future__ import annotations

import numpy as np
from cap_s.models import ProcessedSignal


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
