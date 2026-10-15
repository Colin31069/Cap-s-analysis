from __future__ import annotations

import os
from concurrent.futures import CancelledError
from time import monotonic
from typing import Callable, Sequence

import numpy as np

from .analysis import CapacitanceCache, analyze_signal, check_cancelled, load_capacitance_values
from .config import LINE_STYLE_CYCLE
from .csv_safety import spreadsheet_safe_cell
from .exclusions import current_excluded_file_names, unhonored_excluded_samples
from .filesystem import list_xlsx_files
from .metadata import load_experiment_metadata
from .models import AnalysisProgress, ErrorBandGroup, ErrorBandPayload, ErrorBandSettings, PlotAppearance, ProcessedSignal


ERROR_BAND_UNITS = {
    "Delta": "Baseline-subtracted ΔC (pF)",
    "DeltaPct": "Relative change (%)",
    "Raw": "Capacitance (pF)",
}


ERROR_BAND_COLORS = ("#0072B2", "#009E73", "#E69F00", "#CC79A7", "#D55E00", "#56B4E9", "#332288", "#666666", "#882255", "#44AA99", "#AA4499", "#999933", "#661100", "#6699CC", "#117733", "#AA4466")

LEGEND_POSITIONS = {
    "右側圖外": "outside_right",
    "下方圖外": "outside_bottom",
    "右上角": "upper right",
    "左上角": "upper left",
    "右下角": "lower right",
    "左下角": "lower left",
    "上方中央": "upper center",
    "下方中央": "lower center",
    "不顯示": "hidden",
}


def validate_error_band_settings(settings: ErrorBandSettings) -> None:
    if settings.display_mode not in ERROR_BAND_UNITS:
        raise ValueError("不支援的顯示單位。")
    for name, value, strictly_positive in (
        ("取樣間隔", settings.sample_interval_sec, True),
        ("Baseline 長度", settings.baseline_duration_sec, True),
        ("施加時間", settings.drug_apply_time_sec, False),
        ("搜尋容許範圍", settings.drug_apply_tolerance_sec, False),
        ("Baseline 警示門檻", settings.baseline_warning_threshold_pct, False),
    ):
        if not np.isfinite(value) or value < 0 or (strictly_positive and value == 0):
            raise ValueError(f"{name}必須是{'大於' if strictly_positive else '不小於'} 0 的有限數值。")


def aggregate_error_band(
    group_name: str,
    signals: Sequence[ProcessedSignal],
    sample_names: Sequence[str],
    settings: ErrorBandSettings,
) -> ErrorBandGroup:
    """Compute pointwise statistics only where every included replicate exists."""
    validate_error_band_settings(settings)
    if not signals or len(signals) != len(sample_names):
        raise ValueError("沒有可分析的重複樣本，或樣本名稱數量不符。")
    aligned: list[tuple[np.ndarray, np.ndarray]] = []
    for signal in signals:
        x = signal.time_sec - signal.drop_time
        y = signal.capacitance
        if len(x) != len(y) or len(x) < 2 or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("樣本必須包含至少兩筆有效的時間與電容資料。")
        if np.any(np.diff(x) <= 0):
            raise ValueError("樣本時間必須依序遞增。")
        if settings.display_mode == "Delta":
            y = y - signal.initial_avg
        elif settings.display_mode == "DeltaPct":
            if abs(signal.initial_avg) < 1e-12:
                raise ValueError("Baseline 為 0，無法計算相對變化百分比。")
            y = (y - signal.initial_avg) / signal.initial_avg * 100.
        aligned.append((x, y))

    interval = settings.sample_interval_sec
    first_tick = int(np.ceil(max(x[0] for x, _ in aligned) / interval - 1e-9))
    last_tick = int(np.floor(min(x[-1] for x, _ in aligned) / interval + 1e-9))
    if last_tick <= first_tick or last_tick <= 0:
        raise ValueError("樣本對齊後沒有足夠的共同反應時間，請檢查施加時間與檔案長度。")
    time_sec = np.arange(first_tick, last_tick + 1, dtype=float) * interval
    # Interpolate within the shared interval; never extrapolate or pad short files.
    values = np.vstack([np.interp(time_sec, x, y) for x, y in aligned])
    mean = np.mean(values, axis=0)
    n = len(signals)
    warnings: list[str] = []
    if n > 1:
        sd = np.std(values, axis=0, ddof=1)
        sem = sd / np.sqrt(n)
    else:
        sd = np.full_like(mean, np.nan)
        sem = np.full_like(mean, np.nan)
        warnings.append(f"{group_name}：n=1，只顯示曲線；SD、SEM 無法估計。")
    return ErrorBandGroup(group_name, tuple(sample_names), time_sec, mean, sd, sem, tuple(warnings))


def build_error_band_payload(
    root_path: str,
    group_names: Sequence[str],
    settings: ErrorBandSettings,
    *,
    progress: Callable[[AnalysisProgress], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    data_cache: CapacitanceCache | None = None,
) -> ErrorBandPayload:
    validate_error_band_settings(settings)
    completed = 0
    total = 0

    def report(stage: str, item: str = "", duration_sec: float = 0.0) -> None:
        check_cancelled(cancelled)
        if progress is not None:
            progress(AnalysisProgress(completed, total, stage, item, duration_sec))

    tasks = []
    for name in dict.fromkeys(group_names):
        report("掃描檔案", name)
        files = list_xlsx_files(os.path.join(root_path, name))
        tasks.append((name, files))
        total += len(files)
    groups: list[ErrorBandGroup] = []
    warnings: list[str] = []
    for group_name, files in tasks:
        folder = os.path.join(root_path, group_name)
        report("讀取組別設定", group_name)
        metadata, metadata_warning = load_experiment_metadata(folder)
        if metadata_warning:
            warnings.append(f"{group_name}：metadata 無法讀取，暫不納入此組，請修正後重試。{metadata_warning}")
            completed += len(files)
            continue
        unhonored = unhonored_excluded_samples(metadata.excluded_samples, files)
        if unhonored:
            names = ", ".join(entry.file_name for entry in unhonored)
            warnings.append(f"{group_name}：排除名單與目前樣本數不相容，暫停此組以避免重新納入：{names}")
            completed += len(files)
            continue
        excluded = current_excluded_file_names(metadata.excluded_samples, files)
        signals: list[ProcessedSignal] = []
        sample_names: list[str] = []
        group_warnings: list[str] = []
        for file_name in files:
            label = f"{group_name}/{file_name}"
            report("讀取 Excel", label)
            if file_name in excluded:
                reason = next((entry.reason for entry in metadata.excluded_samples if entry.file_name.casefold() == file_name.casefold()), "")
                group_warnings.append(f"{label}：依既有 metadata 排除。{reason}")
                completed += 1
                continue
            try:
                started = monotonic()
                path = os.path.join(folder, file_name)
                data = data_cache.load(path, cancelled) if data_cache is not None else load_capacitance_values(path, cancelled=cancelled)
                report("讀取完成", label, monotonic() - started)
                started = monotonic()
                report("分析訊號", label)
                signal = analyze_signal(
                    data,
                    baseline_warning_threshold_pct=settings.baseline_warning_threshold_pct,
                    baseline_duration_sec=settings.baseline_duration_sec,
                    drug_apply_time_sec=settings.drug_apply_time_sec,
                    drug_apply_tolerance_sec=settings.drug_apply_tolerance_sec,
                    sample_interval_sec=settings.sample_interval_sec,
                )
                if signal is None or signal.time_sec[-1] <= signal.drop_time:
                    raise ValueError("沒有施加後的資料，請檢查施加時間與檔案長度。")
                if settings.display_mode == "DeltaPct" and abs(signal.initial_avg) < 1e-12:
                    raise ValueError("Baseline 為 0，無法計算百分比。")
            except CancelledError:
                raise
            except Exception as exc:
                group_warnings.append(f"{label}：未納入；{exc}")
                completed += 1
                report("檔案未納入", label)
                continue
            completed += 1
            report("樣本完成", label, monotonic() - started)
            signals.append(signal)
            sample_names.append(file_name)
            group_warnings.extend(f"{label}：{detail}" for detail in signal.timing_warning_details)
            group_warnings.extend(f"{label}：Baseline {detail}" for detail in build_baseline_warning_details(signal))
        report("計算平均與誤差", group_name)
        try:
            group = aggregate_error_band(group_name, signals, sample_names, settings)
        except ValueError as exc:
            warnings.extend(group_warnings)
            warnings.append(f"{group_name}：未繪製；{exc}")
            continue
        groups.append(group)
        warnings.extend(group_warnings)
        warnings.extend(group.warnings)
    report("分析完成")
    return ErrorBandPayload(root_path, settings, tuple(groups), tuple(warnings))


COLOR_GROUP_OPTIONS = {
    "Excel 所在資料夾名稱": "excel_folder",
    "上層資料夾名稱": "parent_folder",
}


def color_group_name(group_name: str, root_path: str, group_by: str) -> str:
    """Group by the actual directory name, independently of units or labels."""
    folder = os.path.normpath(os.path.join(root_path, group_name))
    if group_by == "parent_folder":
        folder = os.path.dirname(folder)
    elif group_by != "excel_folder":
        raise ValueError("不支援的同色分組依據。")
    return os.path.basename(folder) or folder


def resolve_group_colors(groups: Sequence[ErrorBandGroup], appearance: PlotAppearance, root_path: str) -> dict[str, str]:
    colors: dict[str, str] = {}
    shared: dict[str, str] = {}
    custom = appearance.folder_colors if appearance.color_group_by == "excel_folder" else appearance.parent_colors
    for index, group in enumerate(groups):
        if appearance.same_group_color:
            name = color_group_name(group.group_name, root_path, appearance.color_group_by)
            if name not in shared:
                shared[name] = custom.get(name, ERROR_BAND_COLORS[len(shared) % len(ERROR_BAND_COLORS)])
            colors[group.group_name] = shared[name]
        else:
            colors[group.group_name] = appearance.group_colors.get(group.group_name, ERROR_BAND_COLORS[index % len(ERROR_BAND_COLORS)])
    return colors


def render_error_band_plot(ax, payload: ErrorBandPayload, band_type: str = "SD", title: str = "", show_grid: bool = False, *, appearance: PlotAppearance | None = None) -> None:
    if band_type not in ("SD", "SEM"):
        raise ValueError("誤差範圍必須為 SD 或 SEM。")
    appearance = appearance or PlotAppearance()
    if appearance.legend_position not in LEGEND_POSITIONS.values():
        raise ValueError("不支援的圖例位置。")
    if not 1 <= appearance.legend_columns <= 4 or not 6 <= appearance.legend_font_size <= 18:
        raise ValueError("圖例欄數須為 1–4，字級須為 6–18。")
    ax.clear()
    colors = resolve_group_colors(payload.groups, appearance, payload.root_path)
    for index, group in enumerate(payload.groups):
        color = colors[group.group_name]
        error = group.sd if band_type == "SD" else group.sem
        if group.n > 1:
            ax.fill_between(group.time_sec, group.mean - error, group.mean + error, color=color, alpha=.20, linewidth=0)
        ax.plot(group.time_sec, group.mean, color=color, linestyle=LINE_STYLE_CYCLE[index % len(LINE_STYLE_CYCLE)], linewidth=2., label=f"{group.legend_label or group.group_name} (n={group.n})")
    ax.axvline(0., color="#667085", linestyle="--", linewidth=1., alpha=.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ERROR_BAND_UNITS[payload.settings.display_mode])
    ax.set_title(title.strip())
    if show_grid:
        ax.grid(True, alpha=.2)
    else:
        ax.grid(False)
    ax.margins(x=.01)
    if payload.groups:
        if appearance.legend_position != "hidden":
            legend_options = {"frameon": False, "ncol": appearance.legend_columns, "fontsize": appearance.legend_font_size}
            if appearance.legend_position == "outside_right":
                legend_options.update(loc="center left", bbox_to_anchor=(1.02, .5))
            elif appearance.legend_position == "outside_bottom":
                legend_options.update(loc="upper center", bbox_to_anchor=(.5, -.17))
            else:
                legend_options["loc"] = appearance.legend_position
            # Avoid the costly automatic 'best' search over dense curves/bands.
            legend = ax.legend(**legend_options)
            legend.set_draggable(True)
        if appearance.show_error_label:
            ax.text(.015, .98, f"Mean ± {band_type}", transform=ax.transAxes, va="top", color="#667085", fontsize=9)


def write_error_band_csv(payload: ErrorBandPayload, path: str, band_type: str = "SD") -> None:
    import csv

    if band_type not in ("SD", "SEM"):
        raise ValueError("誤差範圍必須為 SD 或 SEM。")
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("group", "time_sec", "n", "mean", "sd", "sem", "band_type", "lower", "upper", "unit", "sample_files", "sample_interval_sec", "baseline_duration_sec", "drug_apply_time_sec", "drug_apply_tolerance_sec", "warnings", "legend_label"))
        for group in payload.groups:
            for time_sec, mean, sd, sem in zip(group.time_sec, group.mean, group.sd, group.sem):
                error = sd if band_type == "SD" else sem
                writer.writerow(tuple(spreadsheet_safe_cell(cell) for cell in (
                    group.group_name, f"{time_sec:.10g}", group.n, mean,
                    sd if group.n > 1 else "", sem if group.n > 1 else "", band_type,
                    mean - error if group.n > 1 else "", mean + error if group.n > 1 else "",
                    ERROR_BAND_UNITS[payload.settings.display_mode], "; ".join(group.sample_names),
                    payload.settings.sample_interval_sec, payload.settings.baseline_duration_sec,
                    payload.settings.drug_apply_time_sec, payload.settings.drug_apply_tolerance_sec,
                    " | ".join(payload.warnings),
                    group.legend_label or group.group_name,
                )))


def build_baseline_warning_details(signal: ProcessedSignal) -> tuple[str, ...]:
    details: list[str] = []
    if signal.baseline_tail_warning_hit:
        details.append(f"尾端均值偏移 {signal.baseline_tail_offset_pct:+.2f}%")
    if signal.baseline_rise_warning_hit:
        details.append(f"連續上升至 {signal.baseline_rise_offset_pct:+.2f}%")
    return tuple(details)
