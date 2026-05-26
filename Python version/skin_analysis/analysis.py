from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .config import (
    BASELINE_RISE_MIN_RUN,
    BASELINE_RISE_ROLLING_POINTS,
    BASELINE_TAIL_POINTS,
    DATA_COL,
    DEFAULT_BASELINE_DURATION_SEC,
    DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    DEFAULT_DRUG_APPLY_TIME_SEC,
    DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
    DROP_SIGMA_THRESHOLD,
    DT_SEC,
    LEGACY_DROP_SEARCH_POINTS,
    PBS_BASELINE_PRE_ROLL_POINTS,
)
from .models import BaselineWarningStatus, CurveSegment, CurveSplit, DropDetectionSource, ProcessedSignal


def read_xlsx_single(path: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception:
        return None

    if DATA_COL not in df.columns:
        return None
    return df[[DATA_COL]].copy()


def _offset_pct(value: float, baseline: float) -> float:
    if abs(baseline) < 1e-12:
        return 0.0
    return ((value / baseline) * 100.0) - 100.0


def _seconds_to_points(duration_sec: float, minimum: int = 0) -> int:
    return max(minimum, int(round(duration_sec / DT_SEC)))


def _first_threshold_crossing(
    samples: np.ndarray,
    threshold: float,
    start_idx: int,
    end_idx: int,
) -> int | None:
    if start_idx >= end_idx:
        return None

    search_range = samples[start_idx:end_idx]
    over_idx = np.where(search_range > threshold)[0]
    if over_idx.size == 0:
        return None
    return start_idx + int(over_idx[0])


def _max_continuous_rise_offset_pct(baseline_segment: np.ndarray, baseline_avg: float) -> float:
    if baseline_segment.size < BASELINE_RISE_ROLLING_POINTS:
        return 0.0

    kernel = np.ones(BASELINE_RISE_ROLLING_POINTS, dtype=float) / BASELINE_RISE_ROLLING_POINTS
    rolling_mean = np.convolve(baseline_segment, kernel, mode="valid")
    if rolling_mean.size < BASELINE_RISE_MIN_RUN:
        return 0.0

    run_length = 1
    max_offset_pct = 0.0

    for index in range(1, len(rolling_mean)):
        if rolling_mean[index] > rolling_mean[index - 1]:
            run_length += 1
            continue

        if run_length >= BASELINE_RISE_MIN_RUN:
            max_offset_pct = max(max_offset_pct, _offset_pct(float(rolling_mean[index - 1]), baseline_avg))
        run_length = 1

    if run_length >= BASELINE_RISE_MIN_RUN:
        max_offset_pct = max(max_offset_pct, _offset_pct(float(rolling_mean[-1]), baseline_avg))

    return max(0.0, max_offset_pct)


def _baseline_warning_status(tail_hit: bool, rise_hit: bool) -> BaselineWarningStatus:
    hit_count = int(tail_hit) + int(rise_hit)
    if hit_count >= 2:
        return "inaccurate"
    if hit_count == 1:
        return "warning"
    return "ok"


def _effective_baseline_points(
    sample_count: int,
    requested_baseline_duration_sec: float,
    apply_window_start_idx: int,
) -> tuple[int, bool]:
    requested_baseline_points = min(
        sample_count,
        _seconds_to_points(max(0.0, requested_baseline_duration_sec), minimum=1),
    )
    if requested_baseline_points <= apply_window_start_idx:
        return requested_baseline_points, False

    shortened_points = min(sample_count, apply_window_start_idx)
    if shortened_points <= 0:
        return min(sample_count, 1), True
    return shortened_points, True


def _build_timing_warning_details(
    requested_baseline_duration_sec: float,
    effective_baseline_duration_sec: float,
    baseline_was_auto_shortened: bool,
    apply_time_sec: float,
    apply_tolerance_sec: float,
    drop_search_fallback_used: bool,
) -> tuple[str, ...]:
    details: list[str] = []

    if baseline_was_auto_shortened:
        if effective_baseline_duration_sec <= DT_SEC:
            details.append(
                "Baseline overlapped the apply window and was clamped to the minimum baseline length."
            )
        else:
            details.append(
                f"Baseline shortened from {requested_baseline_duration_sec:.1f}s to "
                f"{effective_baseline_duration_sec:.1f}s to stay before the apply window."
            )

    if drop_search_fallback_used:
        details.append(
            f"No threshold crossing found within {apply_time_sec:.1f}s +/- {apply_tolerance_sec:.1f}s; "
            "used automatic fallback search."
        )

    return tuple(details)


def _fallback_drop_index(samples: np.ndarray, threshold: float, baseline_end_idx: int) -> int:
    search_end = min(len(samples), baseline_end_idx + LEGACY_DROP_SEARCH_POINTS)
    crossing_idx = _first_threshold_crossing(samples, threshold, baseline_end_idx, search_end)
    if crossing_idx is None:
        return baseline_end_idx
    return crossing_idx


def split_index_from_time_sec(split_time_sec: float, sample_count: int) -> int:
    if sample_count < 2:
        return 0
    requested_index = int(round(max(0.0, float(split_time_sec)) / DT_SEC))
    return max(1, min(sample_count - 1, requested_index))


def _split_index_for_data(curve_split: CurveSplit, sample_count: int) -> int:
    if sample_count < 2:
        return 0
    return max(1, min(sample_count - 1, int(curve_split.split_index)))


def pbs_pre_roll_window_indices(curve_split: CurveSplit, sample_count: int) -> tuple[int, int, int]:
    split_index = _split_index_for_data(curve_split, sample_count)
    if split_index <= 0:
        return 0, 0, 0
    start_index = max(0, split_index - PBS_BASELINE_PRE_ROLL_POINTS)
    return start_index, split_index, split_index - start_index


def _pbs_pre_roll_warning(pre_roll_points: int) -> str | None:
    if pre_roll_points >= PBS_BASELINE_PRE_ROLL_POINTS:
        return None
    return f"PBS baseline pre-roll {pre_roll_points}/{PBS_BASELINE_PRE_ROLL_POINTS} points before split."


def _build_static_segment_signal(
    samples: np.ndarray,
    baseline_warning_threshold_pct: float,
    baseline_duration_sec: float,
) -> ProcessedSignal | None:
    samples = np.asarray(samples, dtype=float)
    if samples.size == 0:
        return None

    warning_threshold_pct = max(0.0, float(baseline_warning_threshold_pct))
    requested_baseline_duration_sec = max(float(baseline_duration_sec), DT_SEC)
    baseline_len = min(
        len(samples),
        _seconds_to_points(requested_baseline_duration_sec, minimum=1),
    )
    baseline_segment = samples[:baseline_len]
    initial_avg = float(np.mean(baseline_segment))
    effective_baseline_duration_sec = baseline_len * DT_SEC

    tail_len = min(len(baseline_segment), BASELINE_TAIL_POINTS)
    tail_mean = float(np.mean(baseline_segment[-tail_len:])) if tail_len > 0 else initial_avg
    tail_offset_pct = _offset_pct(tail_mean, initial_avg)
    rise_offset_pct = _max_continuous_rise_offset_pct(baseline_segment, initial_avg)
    tail_warning_hit = abs(tail_offset_pct) >= warning_threshold_pct
    rise_warning_hit = rise_offset_pct >= warning_threshold_pct
    warning_status = _baseline_warning_status(tail_warning_hit, rise_warning_hit)
    final_avg = float(np.nanmean(samples[-100:])) if len(samples) >= 100 else float("nan")
    delta_raw = final_avg - initial_avg if not np.isnan(final_avg) else float("nan")

    return ProcessedSignal(
        time_sec=np.arange(len(samples), dtype=float) * DT_SEC,
        capacitance=samples,
        drop_time=0.0,
        delta_capacitance=delta_raw,
        initial_avg=initial_avg,
        effective_baseline_points=baseline_len,
        effective_baseline_duration_sec=effective_baseline_duration_sec,
        baseline_was_auto_shortened=False,
        drop_detection_source="window",
        drop_search_fallback_used=False,
        timing_warning_details=(),
        baseline_warning_status=warning_status,
        baseline_tail_offset_pct=tail_offset_pct,
        baseline_rise_offset_pct=rise_offset_pct,
        baseline_tail_warning_hit=tail_warning_hit,
        baseline_rise_warning_hit=rise_warning_hit,
    )


def _samples_for_segment(
    samples: np.ndarray,
    curve_split: CurveSplit | None,
    segment: CurveSegment,
) -> tuple[np.ndarray | None, int]:
    if segment == "full" or curve_split is None:
        if segment == "lanolin":
            return None, 0
        return samples, 0

    split_index = _split_index_for_data(curve_split, len(samples))
    if split_index <= 0:
        return None, 0
    if segment == "lanolin":
        return samples[:split_index], 0
    if segment == "pbs":
        start_index, _split_index, pre_roll_points = pbs_pre_roll_window_indices(curve_split, len(samples))
        return samples[start_index:], pre_roll_points
    return samples, 0


def analyze_signal(
    data: np.ndarray,
    baseline_warning_threshold_pct: float = DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    baseline_duration_sec: float = DEFAULT_BASELINE_DURATION_SEC,
    drug_apply_time_sec: float = DEFAULT_DRUG_APPLY_TIME_SEC,
    drug_apply_tolerance_sec: float = DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
) -> ProcessedSignal | None:
    samples = np.asarray(data, dtype=float)
    if samples.size == 0:
        return None

    warning_threshold_pct = max(0.0, float(baseline_warning_threshold_pct))
    requested_baseline_duration_sec = max(float(baseline_duration_sec), DT_SEC)
    requested_apply_time_sec = max(0.0, float(drug_apply_time_sec))
    requested_apply_tolerance_sec = max(0.0, float(drug_apply_tolerance_sec))

    apply_center_idx = _seconds_to_points(requested_apply_time_sec)
    apply_tolerance_points = _seconds_to_points(requested_apply_tolerance_sec)
    apply_window_start_idx = max(0, apply_center_idx - apply_tolerance_points)
    apply_window_end_idx = min(len(samples), apply_center_idx + apply_tolerance_points + 1)

    baseline_len, baseline_was_auto_shortened = _effective_baseline_points(
        len(samples),
        requested_baseline_duration_sec,
        apply_window_start_idx,
    )
    baseline_segment = samples[:baseline_len]
    initial_avg = float(np.mean(baseline_segment))
    sample_std = float(np.std(baseline_segment, ddof=1)) if baseline_len > 1 else 0.0
    effective_baseline_duration_sec = baseline_len * DT_SEC

    tail_len = min(len(baseline_segment), BASELINE_TAIL_POINTS)
    tail_mean = float(np.mean(baseline_segment[-tail_len:])) if tail_len > 0 else initial_avg
    tail_offset_pct = _offset_pct(tail_mean, initial_avg)
    rise_offset_pct = _max_continuous_rise_offset_pct(baseline_segment, initial_avg)
    tail_warning_hit = abs(tail_offset_pct) >= warning_threshold_pct
    rise_warning_hit = rise_offset_pct >= warning_threshold_pct
    warning_status = _baseline_warning_status(tail_warning_hit, rise_warning_hit)

    threshold = initial_avg + DROP_SIGMA_THRESHOLD * max(sample_std, 1e-4)
    window_search_start_idx = max(baseline_len, apply_window_start_idx)
    idx_drop = _first_threshold_crossing(
        samples,
        threshold,
        window_search_start_idx,
        apply_window_end_idx,
    )
    drop_detection_source: DropDetectionSource = "window"
    drop_search_fallback_used = idx_drop is None

    if idx_drop is None:
        idx_drop = _fallback_drop_index(samples, threshold, baseline_len)
        drop_detection_source = "fallback_auto"

    final_avg = float(np.nanmean(samples[-100:])) if len(samples) >= 100 else float("nan")
    delta_raw = final_avg - initial_avg if not np.isnan(final_avg) else float("nan")
    timing_warning_details = _build_timing_warning_details(
        requested_baseline_duration_sec=requested_baseline_duration_sec,
        effective_baseline_duration_sec=effective_baseline_duration_sec,
        baseline_was_auto_shortened=baseline_was_auto_shortened,
        apply_time_sec=requested_apply_time_sec,
        apply_tolerance_sec=requested_apply_tolerance_sec,
        drop_search_fallback_used=drop_search_fallback_used,
    )

    return ProcessedSignal(
        time_sec=np.arange(len(samples), dtype=float) * DT_SEC,
        capacitance=samples,
        drop_time=idx_drop * DT_SEC,
        delta_capacitance=delta_raw,
        initial_avg=initial_avg,
        effective_baseline_points=baseline_len,
        effective_baseline_duration_sec=effective_baseline_duration_sec,
        baseline_was_auto_shortened=baseline_was_auto_shortened,
        drop_detection_source=drop_detection_source,
        drop_search_fallback_used=drop_search_fallback_used,
        timing_warning_details=timing_warning_details,
        baseline_warning_status=warning_status,
        baseline_tail_offset_pct=tail_offset_pct,
        baseline_rise_offset_pct=rise_offset_pct,
        baseline_tail_warning_hit=tail_warning_hit,
        baseline_rise_warning_hit=rise_warning_hit,
    )


def process_single_file(
    file_path: str,
    baseline_warning_threshold_pct: float = DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    baseline_duration_sec: float = DEFAULT_BASELINE_DURATION_SEC,
    drug_apply_time_sec: float = DEFAULT_DRUG_APPLY_TIME_SEC,
    drug_apply_tolerance_sec: float = DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
    curve_split: CurveSplit | None = None,
    segment: CurveSegment = "pbs",
) -> ProcessedSignal | None:
    df = read_xlsx_single(file_path)
    if df is None or df.empty:
        return None
    samples = df[DATA_COL].to_numpy()
    segment_samples, pre_roll_points = _samples_for_segment(samples, curve_split, segment)
    if segment_samples is None or len(segment_samples) == 0:
        return None
    if segment == "lanolin":
        return _build_static_segment_signal(
            segment_samples,
            baseline_warning_threshold_pct=baseline_warning_threshold_pct,
            baseline_duration_sec=baseline_duration_sec,
        )
    adjusted_baseline_duration_sec = baseline_duration_sec
    adjusted_drug_apply_time_sec = drug_apply_time_sec
    pre_roll_warning = None
    if segment == "pbs" and curve_split is not None:
        adjusted_baseline_duration_sec = PBS_BASELINE_PRE_ROLL_POINTS * DT_SEC
        adjusted_drug_apply_time_sec = drug_apply_time_sec + (pre_roll_points * DT_SEC)
        pre_roll_warning = _pbs_pre_roll_warning(pre_roll_points)

    signal = analyze_signal(
        segment_samples,
        baseline_warning_threshold_pct=baseline_warning_threshold_pct,
        baseline_duration_sec=adjusted_baseline_duration_sec,
        drug_apply_time_sec=adjusted_drug_apply_time_sec,
        drug_apply_tolerance_sec=drug_apply_tolerance_sec,
    )
    if signal is None or pre_roll_warning is None:
        return signal
    return replace(
        signal,
        timing_warning_details=(pre_roll_warning, *signal.timing_warning_details),
    )
