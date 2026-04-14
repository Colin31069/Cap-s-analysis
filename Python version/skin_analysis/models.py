from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BaselineWarningStatus = Literal["ok", "warning", "inaccurate"]
DropDetectionSource = Literal["window", "fallback_auto"]


@dataclass(frozen=True)
class MedicineEntry:
    name: str
    dose: str


@dataclass(frozen=True)
class ExperimentMetadata:
    medicine_count: int
    medicines: list[MedicineEntry]


@dataclass(frozen=True)
class ProcessedSignal:
    time_sec: FloatArray
    capacitance: FloatArray
    drop_time: float
    delta_capacitance: float
    initial_avg: float
    effective_baseline_points: int
    effective_baseline_duration_sec: float
    baseline_was_auto_shortened: bool
    drop_detection_source: DropDetectionSource
    drop_search_fallback_used: bool
    timing_warning_details: tuple[str, ...]
    baseline_warning_status: BaselineWarningStatus
    baseline_tail_offset_pct: float
    baseline_rise_offset_pct: float
    baseline_tail_warning_hit: bool
    baseline_rise_warning_hit: bool


@dataclass(frozen=True)
class PlotSettings:
    experiment_name: str
    target_dir: str
    all_files: list[str]
    metadata: ExperimentMetadata
    is_overlay: bool
    display_mode: str
    use_group_color: bool
    show_drop_lines: bool
    leg_style: str
    show_base: bool
    show_delta: bool
    baseline_duration_sec: float
    drug_apply_time_sec: float
    drug_apply_tolerance_sec: float
    baseline_warning_threshold_pct: float


@dataclass(frozen=True)
class PlotItem:
    sample_name: str
    x_plot: FloatArray
    y_plot: FloatArray
    label_txt: str
    drop_time: float
    line_style: str
    line_color: Any | None
    effective_baseline_duration_sec: float
    drop_detection_source: DropDetectionSource
    timing_warning_details: tuple[str, ...]
    baseline_warning_status: BaselineWarningStatus
    baseline_warning_details: tuple[str, ...]


@dataclass(frozen=True)
class PlotPayload:
    settings: PlotSettings
    title: str
    y_unit: str
    plot_items: list[PlotItem]
