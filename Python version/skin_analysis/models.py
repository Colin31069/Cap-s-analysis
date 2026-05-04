from __future__ import annotations

from dataclasses import dataclass, field
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
class ExcludedSample:
    file_name: str
    reason: str = ""


@dataclass(frozen=True)
class ExperimentMetadata:
    medicine_count: int
    medicines: list[MedicineEntry]
    excluded_samples: list[ExcludedSample] = field(default_factory=list)


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
    custom_title: str = ""


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


@dataclass(frozen=True)
class StatisticalSample:
    group_name: str
    sample_name: str
    delta_percent: float
    delta_capacitance: float
    baseline: float
    drop_time: float
    baseline_warning_status: BaselineWarningStatus
    drop_detection_source: DropDetectionSource
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class StatisticalExclusion:
    group_name: str
    file_name: str
    reason: str


@dataclass(frozen=True)
class GroupStatistics:
    group_name: str
    n: int
    mean: float
    sd: float
    sem: float
    median: float
    q1: float
    q3: float
    iqr: float
    ci95_low: float
    ci95_high: float
    shapiro_statistic: float
    shapiro_p_value: float
    normality_note: str


@dataclass(frozen=True)
class VarianceCheckResult:
    method: str
    statistic: float
    p_value: float
    note: str


@dataclass(frozen=True)
class AnovaResult:
    method: str
    group_count: int
    sample_count: int
    statistic: float
    df_num: float
    df_den: float
    p_value: float
    eta_squared: float
    omega_squared: float
    note: str


@dataclass(frozen=True)
class StatisticalAnalysisResult:
    root_path: str
    samples: list[StatisticalSample]
    group_statistics: list[GroupStatistics]
    variance_check: VarianceCheckResult
    anova: AnovaResult
    warnings: tuple[str, ...]
    scipy_available: bool
    excluded_samples: list[StatisticalExclusion] = field(default_factory=list)
