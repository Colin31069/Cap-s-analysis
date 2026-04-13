from __future__ import annotations

import os
from itertools import cycle
from typing import Any

import numpy as np

from .analysis import process_single_file
from .config import INITIAL_BASELINE_POINTS, LINE_STYLE_CYCLE
from .models import ExperimentMetadata, PlotItem, PlotPayload, PlotSettings, ProcessedSignal


def display_mode_to_y_unit(display_mode: str) -> str:
    if display_mode == "Norm":
        return "Normalized (%)"
    if display_mode == "Base":
        return "Baseline Capacitance (pF)"
    return "Raw Capacitance (pF)"


def transform_signal_for_display(
    signal: ProcessedSignal,
    display_mode: str,
) -> tuple[np.ndarray, np.ndarray, str]:
    # Align plotted time to the detected drop so overlayed traces share t=0.
    x_plot = signal.time_sec - signal.drop_time
    y_plot = signal.capacitance
    base = signal.initial_avg
    delta_raw = signal.delta_capacitance

    if display_mode == "Norm":
        y_plot = (signal.capacitance / base) * 100
        delta_pct = (((base + delta_raw) / base) * 100) - 100
        delta_str = f"Δ:{delta_pct:.2f}%"
    elif display_mode == "Base":
        limit = min(INITIAL_BASELINE_POINTS, len(signal.capacitance))
        x_plot = x_plot[:limit]
        y_plot = signal.capacitance[:limit]
        delta_str = f"Δ:{delta_raw:.2f}pF"
    else:
        delta_str = f"Δ:{delta_raw:.2f}pF"

    return x_plot, y_plot, delta_str


def build_legend_label(sample_name: str, settings: PlotSettings, base: float, delta_str: str) -> str:
    if settings.leg_style == "Simple":
        return f"N {sample_name}"

    parts = [f"N {sample_name}"]
    info_parts: list[str] = []
    if settings.show_base:
        info_parts.append(f"Base:{base:.2f} pF")
    if settings.show_delta:
        info_parts.append(delta_str)

    if info_parts:
        return " ".join(parts) + " (" + ", ".join(info_parts) + ")"
    return " ".join(parts)


def build_plot_title(experiment_name: str, metadata: ExperimentMetadata) -> str:
    title_parts = [experiment_name]
    for entry in metadata.medicines[: metadata.medicine_count]:
        name = entry.name.strip()
        dose = entry.dose.strip()
        if not name and not dose:
            continue
        if name and dose:
            title_parts.append(f"{name}: {dose}")
        elif name:
            title_parts.append(name)
        else:
            title_parts.append(dose)
    return " | ".join(title_parts)


def build_plot_item(
    signal: ProcessedSignal,
    sample_name: str,
    settings: PlotSettings,
    line_style: str,
    line_color: Any | None,
) -> PlotItem:
    x_plot, y_plot, delta_str = transform_signal_for_display(signal, settings.display_mode)
    label_txt = build_legend_label(sample_name, settings, signal.initial_avg, delta_str)
    return PlotItem(
        x_plot=x_plot,
        y_plot=y_plot,
        label_txt=label_txt,
        drop_time=0.0,
        line_style=line_style,
        line_color=line_color,
    )


def build_plot_payload(settings: PlotSettings, group_color: Any | None) -> PlotPayload:
    style_cycler = cycle(LINE_STYLE_CYCLE)
    plot_items: list[PlotItem] = []

    for fname in settings.all_files:
        file_path = os.path.join(settings.target_dir, fname)
        signal = process_single_file(file_path)
        if signal is None:
            continue

        line_style = next(style_cycler) if settings.use_group_color else "-"
        line_color = group_color if settings.use_group_color else None
        sample_name = os.path.splitext(fname)[0]
        plot_items.append(build_plot_item(signal, sample_name, settings, line_style, line_color))

    return PlotPayload(
        settings=settings,
        title=build_plot_title(settings.experiment_name, settings.metadata),
        y_unit=display_mode_to_y_unit(settings.display_mode),
        plot_items=plot_items,
    )
