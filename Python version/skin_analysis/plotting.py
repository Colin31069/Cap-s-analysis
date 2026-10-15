from __future__ import annotations

import os
from itertools import cycle
from typing import Any

import numpy as np

from .analysis import process_single_file
from .config import LINE_STYLE_CYCLE
from .exclusions import current_excluded_file_names
from .metadata import curve_split_for_file, drop_time_override_for_file
from .models import BaselineWarningStatus, ExperimentMetadata, PlotItem, PlotPayload, PlotSettings, ProcessedSignal

NO_LEGEND_LABEL = "_nolegend_"


def display_mode_to_y_unit(display_mode: str) -> str:
    if display_mode == "Norm":
        return "Normalized (%)"
    if display_mode == "Base":
        return "Baseline Capacitance (pF)"
    return "Raw Capacitance (pF)"


def transform_signal_for_display(
    signal: ProcessedSignal,
    display_mode: str,
    display_drop_time_sec: float | None = None,
) -> tuple[np.ndarray, np.ndarray, str]:
    # Align plotted time to the detected drop so overlayed traces share t=0.
    drop_time_sec = signal.drop_time if display_drop_time_sec is None else display_drop_time_sec
    x_plot = signal.time_sec - drop_time_sec
    y_plot = signal.capacitance
    base = signal.initial_avg
    delta_raw = signal.delta_capacitance

    if display_mode == "Norm":
        y_plot = (signal.capacitance / base) * 100
        delta_pct = (((base + delta_raw) / base) * 100) - 100
        delta_str = f"Δ:{delta_pct:.2f}%"
    elif display_mode == "Base":
        limit = min(signal.effective_baseline_points, len(signal.capacitance))
        x_plot = x_plot[:limit]
        y_plot = signal.capacitance[:limit]
        delta_str = f"Δ:{delta_raw:.2f}pF"
    else:
        delta_str = f"Δ:{delta_raw:.2f}pF"

    return x_plot, y_plot, delta_str


def build_baseline_warning_details(signal: ProcessedSignal) -> tuple[str, ...]:
    details: list[str] = []
    if signal.baseline_tail_warning_hit:
        details.append(f"尾端均值偏移 {signal.baseline_tail_offset_pct:+.2f}%")
    if signal.baseline_rise_warning_hit:
        details.append(f"連續上升至 {signal.baseline_rise_offset_pct:+.2f}%")
    return tuple(details)


def warning_status_suffix(status: BaselineWarningStatus) -> str:
    if status == "warning":
        return " [warning]"
    if status == "inaccurate":
        return " [inaccurate]"
    return ""


def build_medicine_legend_summary(metadata: ExperimentMetadata) -> str:
    parts: list[str] = []
    for entry in metadata.medicines[: metadata.medicine_count]:
        name = entry.name.strip()
        dose = entry.dose.strip()
        if name and dose:
            parts.append(f"{name} {dose}")
        elif name:
            parts.append(name)
        elif dose:
            parts.append(dose)
    return " / ".join(parts)


def build_overlay_legend_group_label(settings: PlotSettings) -> str:
    medicine_summary = build_medicine_legend_summary(settings.metadata)
    if medicine_summary:
        return medicine_summary
    return settings.experiment_name.strip()


def build_legend_label(
    sample_name: str,
    settings: PlotSettings,
    base: float,
    delta_str: str,
    warning_status: BaselineWarningStatus,
) -> str:
    if settings.is_overlay and settings.use_group_color:
        return NO_LEGEND_LABEL

    if settings.leg_style == "Simple":
        return f"N {sample_name}"

    prefix = f"N {sample_name}{warning_status_suffix(warning_status)}"

    info_parts: list[str] = []
    if settings.show_base:
        info_parts.append(f"Base:{base:.2f} pF")
    if settings.show_delta:
        info_parts.append(delta_str)

    if info_parts:
        return prefix + " (" + ", ".join(info_parts) + ")"
    return prefix


def build_plot_title(
    experiment_name: str,
    metadata: ExperimentMetadata,
    custom_title: str = "",
) -> str:
    custom_title = custom_title.strip()
    if custom_title:
        return custom_title

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


def analysis_segment_title_suffix(display_segment: str) -> str:
    if display_segment == "pbs":
        return "PBS Segment"
    if display_segment == "lanolin":
        return "Lanolin Segment"
    return "Full Curve"


def build_plot_item(
    signal: ProcessedSignal,
    file_name: str,
    sample_name: str,
    settings: PlotSettings,
    line_style: str,
    line_color: Any | None,
    display_drop_time_sec: float | None = None,
    manual_drop_time: bool = False,
) -> PlotItem:
    x_plot, y_plot, delta_str = transform_signal_for_display(
        signal,
        settings.display_mode,
        display_drop_time_sec=display_drop_time_sec,
    )
    label_txt = build_legend_label(
        sample_name,
        settings,
        signal.initial_avg,
        delta_str,
        signal.baseline_warning_status,
    )
    if manual_drop_time and settings.leg_style != "Simple" and label_txt != NO_LEGEND_LABEL:
        label_txt = f"{label_txt} [manual drop]"
    return PlotItem(
        file_name=file_name,
        sample_name=sample_name,
        x_plot=x_plot,
        y_plot=y_plot,
        label_txt=label_txt,
        drop_time=0.0,
        display_drop_time_sec=signal.drop_time if display_drop_time_sec is None else display_drop_time_sec,
        manual_drop_time=manual_drop_time,
        line_style=line_style,
        line_color=line_color,
        effective_baseline_duration_sec=signal.effective_baseline_duration_sec,
        drop_detection_source=signal.drop_detection_source,
        timing_warning_details=signal.timing_warning_details,
        baseline_warning_status=signal.baseline_warning_status,
        baseline_warning_details=build_baseline_warning_details(signal),
    )


def build_plot_payload(settings: PlotSettings, group_color: Any | None) -> PlotPayload:
    style_cycler = cycle(LINE_STYLE_CYCLE)
    plot_items: list[PlotItem] = []
    excluded_file_names = current_excluded_file_names(settings.metadata.excluded_samples, settings.all_files)

    for fname in settings.all_files:
        if fname in excluded_file_names:
            continue

        file_path = os.path.join(settings.target_dir, fname)
        curve_split = curve_split_for_file(settings.metadata, fname)
        signal = process_single_file(
            file_path,
            baseline_warning_threshold_pct=settings.baseline_warning_threshold_pct,
            baseline_duration_sec=settings.baseline_duration_sec,
            drug_apply_time_sec=settings.drug_apply_time_sec,
            drug_apply_tolerance_sec=settings.drug_apply_tolerance_sec,
            curve_split=curve_split,
            segment=settings.analysis_segment,
        )
        if signal is None:
            continue

        line_style = next(style_cycler) if settings.use_group_color else "-"
        line_color = group_color if settings.use_group_color else None
        sample_name = os.path.splitext(fname)[0]
        drop_override = drop_time_override_for_file(settings.metadata, fname, settings.analysis_segment)
        display_drop_time_sec = drop_override.drop_time_sec if drop_override is not None else signal.drop_time
        plot_items.append(
            build_plot_item(
                signal,
                fname,
                sample_name,
                settings,
                line_style,
                line_color,
                display_drop_time_sec=display_drop_time_sec,
                manual_drop_time=drop_override is not None,
            )
        )

    return PlotPayload(
        settings=settings,
        title=(
            f"{build_plot_title(settings.experiment_name, settings.metadata)} | "
            f"{analysis_segment_title_suffix(settings.analysis_segment)}"
        ),
        y_unit=display_mode_to_y_unit(settings.display_mode),
        plot_items=plot_items,
    )
