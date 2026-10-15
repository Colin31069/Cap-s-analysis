from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any, Literal

import numpy as np

from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

BaselineWarningStatus = Literal["ok", "warning", "inaccurate"]

DropDetectionSource = Literal["window", "fallback_auto"]

DixonQSide = Literal["low", "high"]

@dataclass(frozen=True)
class MedicineEntry:
    name: str
    dose: str

@dataclass(frozen=True)
class ExcludedSample:
    file_name: str
    reason: str = ""
    method: str = ""

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
class ErrorBandSettings:
    display_mode: str = "Delta"
    sample_interval_sec: float = 0.1
    baseline_duration_sec: float = 20.0
    drug_apply_time_sec: float = 25.0
    drug_apply_tolerance_sec: float = 5.0
    baseline_warning_threshold_pct: float = 2.0


@dataclass(frozen=True)
class AnalysisProgress:
    completed: int
    total: int
    stage: str
    item: str = ""
    duration_sec: float = 0.0


@dataclass(frozen=True)
class PlotAppearance:
    group_colors: dict[str, str] = field(default_factory=dict)
    legend_position: str = "outside_right"
    legend_columns: int = 1
    legend_font_size: int = 9
    show_error_label: bool = False
    same_group_color: bool = False
    parent_colors: dict[str, str] = field(default_factory=dict)
    color_group_by: Literal["excel_folder", "parent_folder"] = "parent_folder"
    folder_colors: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class ErrorBandGroup:
    group_name: str
    sample_names: tuple[str, ...]
    time_sec: FloatArray
    mean: FloatArray
    sd: FloatArray
    sem: FloatArray
    warnings: tuple[str, ...] = ()
    legend_label: str = ""

    @property
    def n(self) -> int:
        return len(self.sample_names)

@dataclass(frozen=True)
class ErrorBandPayload:
    root_path: str
    settings: ErrorBandSettings
    groups: tuple[ErrorBandGroup, ...]
    warnings: tuple[str, ...] = ()
