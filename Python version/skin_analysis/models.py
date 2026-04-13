from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


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


@dataclass(frozen=True)
class PlotItem:
    x_plot: FloatArray
    y_plot: FloatArray
    label_txt: str
    drop_time: float
    line_style: str
    line_color: Any | None


@dataclass(frozen=True)
class PlotPayload:
    settings: PlotSettings
    title: str
    y_unit: str
    plot_items: list[PlotItem]
