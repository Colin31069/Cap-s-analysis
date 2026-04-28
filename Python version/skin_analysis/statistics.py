from __future__ import annotations

import csv
import math
import os
from collections.abc import Iterable, Sequence

import numpy as np

from .analysis import process_single_file
from .config import (
    DEFAULT_BASELINE_DURATION_SEC,
    DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    DEFAULT_DRUG_APPLY_TIME_SEC,
    DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
)
from .filesystem import get_subfolders, list_xlsx_files
from .models import (
    AnovaResult,
    GroupStatistics,
    ProcessedSignal,
    StatisticalAnalysisResult,
    StatisticalSample,
    VarianceCheckResult,
)

try:
    from scipy import stats as scipy_stats
except ImportError:  # pragma: no cover - exercised in environments without scipy
    scipy_stats = None

SCIPY_AVAILABLE = scipy_stats is not None
MISSING_SCIPY_NOTE = "SciPy is not installed; p-values and 95% CIs are unavailable."


def _nan() -> float:
    return float("nan")


def _is_finite(value: float) -> bool:
    return math.isfinite(float(value))


def _format_float(value: float, digits: int = 4) -> str:
    if not _is_finite(value):
        return "NA"
    return f"{value:.{digits}g}"


def delta_percent_from_signal(signal: ProcessedSignal) -> float:
    if abs(signal.initial_avg) < 1e-12 or not _is_finite(signal.delta_capacitance):
        return _nan()
    return (signal.delta_capacitance / signal.initial_avg) * 100.0


def _values_for_group(samples: Sequence[StatisticalSample], group_name: str) -> np.ndarray:
    values = [sample.delta_percent for sample in samples if sample.group_name == group_name]
    return np.asarray(values, dtype=float)


def _valid_groups(samples: Sequence[StatisticalSample]) -> list[str]:
    seen: list[str] = []
    for sample in samples:
        if sample.group_name not in seen:
            seen.append(sample.group_name)
    return seen


def summarize_group(group_name: str, values: Sequence[float]) -> GroupStatistics:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)

    if n == 0:
        return GroupStatistics(
            group_name=group_name,
            n=0,
            mean=_nan(),
            sd=_nan(),
            sem=_nan(),
            median=_nan(),
            q1=_nan(),
            q3=_nan(),
            iqr=_nan(),
            ci95_low=_nan(),
            ci95_high=_nan(),
            shapiro_statistic=_nan(),
            shapiro_p_value=_nan(),
            normality_note="No valid samples.",
        )

    mean = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if n >= 2 else _nan()
    sem = float(sd / math.sqrt(n)) if n >= 2 and _is_finite(sd) else _nan()
    median = float(np.median(arr))
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    ci95_low = _nan()
    ci95_high = _nan()
    if n >= 2 and scipy_stats is not None and _is_finite(sem):
        t_crit = float(scipy_stats.t.ppf(0.975, df=n - 1))
        ci95_low = mean - t_crit * sem
        ci95_high = mean + t_crit * sem

    shapiro_statistic = _nan()
    shapiro_p_value = _nan()
    if n < 3:
        normality_note = "Normality not tested because n < 3."
    elif scipy_stats is None:
        normality_note = MISSING_SCIPY_NOTE
    else:
        shapiro_result = scipy_stats.shapiro(arr)
        shapiro_statistic = float(shapiro_result.statistic)
        shapiro_p_value = float(shapiro_result.pvalue)
        normality_note = "Shapiro-Wilk normality check."

    return GroupStatistics(
        group_name=group_name,
        n=n,
        mean=mean,
        sd=sd,
        sem=sem,
        median=median,
        q1=q1,
        q3=q3,
        iqr=iqr,
        ci95_low=ci95_low,
        ci95_high=ci95_high,
        shapiro_statistic=shapiro_statistic,
        shapiro_p_value=shapiro_p_value,
        normality_note=normality_note,
    )


def _classical_anova_effects(group_values: Sequence[np.ndarray]) -> tuple[float, float, float, float, float, float]:
    valid = [values[np.isfinite(values)] for values in group_values if values[np.isfinite(values)].size > 0]
    if len(valid) < 2:
        return _nan(), _nan(), _nan(), _nan(), _nan(), _nan()

    all_values = np.concatenate(valid)
    sample_count = int(all_values.size)
    group_count = len(valid)
    if sample_count <= group_count:
        return _nan(), _nan(), _nan(), _nan(), _nan(), _nan()

    grand_mean = float(np.mean(all_values))
    ss_between = float(sum(len(values) * ((float(np.mean(values)) - grand_mean) ** 2) for values in valid))
    ss_within = float(sum(np.sum((values - float(np.mean(values))) ** 2) for values in valid))
    ss_total = ss_between + ss_within
    df_between = float(group_count - 1)
    df_within = float(sample_count - group_count)
    ms_within = ss_within / df_within if df_within > 0 else _nan()
    eta_squared = ss_between / ss_total if ss_total > 0 else _nan()
    if ss_total > 0 and _is_finite(ms_within):
        omega_squared = max(0.0, (ss_between - (df_between * ms_within)) / (ss_total + ms_within))
    else:
        omega_squared = _nan()
    return ss_between, ss_within, df_between, df_within, eta_squared, omega_squared


def compute_variance_check(group_statistics: Sequence[GroupStatistics], samples: Sequence[StatisticalSample]) -> VarianceCheckResult:
    group_values = [
        _values_for_group(samples, group.group_name)
        for group in group_statistics
        if group.n >= 2
    ]
    if len(group_values) < 2:
        return VarianceCheckResult(
            method="Brown-Forsythe",
            statistic=_nan(),
            p_value=_nan(),
            note="Variance check not run because at least two groups need n >= 2.",
        )
    if scipy_stats is None:
        return VarianceCheckResult(
            method="Brown-Forsythe",
            statistic=_nan(),
            p_value=_nan(),
            note=MISSING_SCIPY_NOTE,
        )

    absolute_deviations = np.concatenate([
        np.abs(values - float(np.median(values)))
        for values in group_values
    ])
    if absolute_deviations.size == 0 or float(np.var(absolute_deviations)) <= 1e-15:
        return VarianceCheckResult(
            method="Brown-Forsythe",
            statistic=_nan(),
            p_value=_nan(),
            note="Variance check not run because median-centered deviations are identical.",
        )

    test_result = scipy_stats.levene(*group_values, center="median")
    return VarianceCheckResult(
        method="Brown-Forsythe",
        statistic=float(test_result.statistic),
        p_value=float(test_result.pvalue),
        note="Levene variance check centered on group medians.",
    )


def compute_one_way_anova(group_statistics: Sequence[GroupStatistics], samples: Sequence[StatisticalSample]) -> AnovaResult:
    group_values = [
        _values_for_group(samples, group.group_name)
        for group in group_statistics
        if group.n >= 2
    ]
    sample_count = int(sum(len(values) for values in group_values))
    group_count = len(group_values)
    ss_between, ss_within, df_between, df_within, eta_squared, omega_squared = _classical_anova_effects(group_values)

    if group_count < 2 or sample_count <= group_count:
        return AnovaResult(
            method="One-way ANOVA",
            group_count=group_count,
            sample_count=sample_count,
            statistic=_nan(),
            df_num=df_between,
            df_den=df_within,
            p_value=_nan(),
            eta_squared=eta_squared,
            omega_squared=omega_squared,
            note="ANOVA not run because at least two groups need n >= 2.",
        )

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    if ms_within <= 0:
        statistic = _nan()
        p_value = _nan()
        note = "ANOVA not run because within-group variance is zero."
    else:
        statistic = ms_between / ms_within
        if scipy_stats is None:
            p_value = _nan()
            note = MISSING_SCIPY_NOTE
        else:
            p_value = float(scipy_stats.f.sf(statistic, df_between, df_within))
            note = "Classical one-way ANOVA."

    return AnovaResult(
        method="One-way ANOVA",
        group_count=group_count,
        sample_count=sample_count,
        statistic=statistic,
        df_num=df_between,
        df_den=df_within,
        p_value=p_value,
        eta_squared=eta_squared,
        omega_squared=omega_squared,
        note=note,
    )


def analyze_delta_percent_samples(
    samples: Sequence[StatisticalSample],
    root_path: str = "",
) -> StatisticalAnalysisResult:
    groups = _valid_groups(samples)
    group_statistics = [
        summarize_group(group, _values_for_group(samples, group))
        for group in groups
    ]
    warnings: list[str] = []

    if not SCIPY_AVAILABLE:
        warnings.append(MISSING_SCIPY_NOTE)
    for summary in group_statistics:
        if summary.n < 2:
            warnings.append(f"Group '{summary.group_name}' has n={summary.n}; one-way ANOVA needs n >= 2.")
        elif summary.n < 3:
            warnings.append(f"Group '{summary.group_name}' has n={summary.n}; Shapiro-Wilk normality needs n >= 3.")

    variance_check = compute_variance_check(group_statistics, samples)
    anova = compute_one_way_anova(group_statistics, samples)

    return StatisticalAnalysisResult(
        root_path=root_path,
        samples=list(samples),
        group_statistics=group_statistics,
        variance_check=variance_check,
        anova=anova,
        warnings=tuple(warnings),
        scipy_available=SCIPY_AVAILABLE,
    )


def collect_delta_percent_samples(
    root_path: str,
    baseline_warning_threshold_pct: float = DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    baseline_duration_sec: float = DEFAULT_BASELINE_DURATION_SEC,
    drug_apply_time_sec: float = DEFAULT_DRUG_APPLY_TIME_SEC,
    drug_apply_tolerance_sec: float = DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
) -> tuple[list[StatisticalSample], tuple[str, ...]]:
    samples: list[StatisticalSample] = []
    warnings: list[str] = []
    for group_name in get_subfolders(root_path):
        group_dir = os.path.join(root_path, group_name)
        files = list_xlsx_files(group_dir)
        if not files:
            warnings.append(f"Group '{group_name}' has no .xlsx files.")
            continue

        for file_name in files:
            file_path = os.path.join(group_dir, file_name)
            signal = process_single_file(
                file_path,
                baseline_warning_threshold_pct=baseline_warning_threshold_pct,
                baseline_duration_sec=baseline_duration_sec,
                drug_apply_time_sec=drug_apply_time_sec,
                drug_apply_tolerance_sec=drug_apply_tolerance_sec,
            )
            sample_name = os.path.splitext(file_name)[0]
            if signal is None:
                warnings.append(f"{group_name}/{file_name} could not be analyzed.")
                continue

            delta_percent = delta_percent_from_signal(signal)
            if not _is_finite(delta_percent):
                warnings.append(f"{group_name}/{file_name} has an invalid Delta % and was skipped.")
                continue

            sample_warnings: list[str] = []
            if signal.baseline_warning_status != "ok":
                sample_warnings.append(f"baseline {signal.baseline_warning_status}")
            if signal.timing_warning_details:
                sample_warnings.extend(signal.timing_warning_details)

            samples.append(
                StatisticalSample(
                    group_name=group_name,
                    sample_name=sample_name,
                    delta_percent=delta_percent,
                    delta_capacitance=signal.delta_capacitance,
                    baseline=signal.initial_avg,
                    drop_time=signal.drop_time,
                    baseline_warning_status=signal.baseline_warning_status,
                    drop_detection_source=signal.drop_detection_source,
                    warnings=tuple(sample_warnings),
                )
            )

    return samples, tuple(warnings)


def build_statistical_analysis(
    root_path: str,
    baseline_warning_threshold_pct: float = DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
    baseline_duration_sec: float = DEFAULT_BASELINE_DURATION_SEC,
    drug_apply_time_sec: float = DEFAULT_DRUG_APPLY_TIME_SEC,
    drug_apply_tolerance_sec: float = DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
) -> StatisticalAnalysisResult:
    samples, collection_warnings = collect_delta_percent_samples(
        root_path,
        baseline_warning_threshold_pct=baseline_warning_threshold_pct,
        baseline_duration_sec=baseline_duration_sec,
        drug_apply_time_sec=drug_apply_time_sec,
        drug_apply_tolerance_sec=drug_apply_tolerance_sec,
    )
    result = analyze_delta_percent_samples(samples, root_path=root_path)
    return StatisticalAnalysisResult(
        root_path=result.root_path,
        samples=result.samples,
        group_statistics=result.group_statistics,
        variance_check=result.variance_check,
        anova=result.anova,
        warnings=tuple(collection_warnings) + result.warnings,
        scipy_available=result.scipy_available,
    )


def _format_descriptive_line(summary: GroupStatistics) -> str:
    return (
        f"{summary.group_name}: n={summary.n}, mean={_format_float(summary.mean)}%, "
        f"SD={_format_float(summary.sd)}%, SEM={_format_float(summary.sem)}%, "
        f"median={_format_float(summary.median)}%, IQR={_format_float(summary.iqr)}%, "
        f"95% CI [{_format_float(summary.ci95_low)}%, {_format_float(summary.ci95_high)}%]"
    )


def _format_anova_line(result: AnovaResult) -> str:
    return (
        f"{result.method}: F={_format_float(result.statistic)}, "
        f"df=({_format_float(result.df_num)}, {_format_float(result.df_den)}), "
        f"p={_format_float(result.p_value)}, eta2={_format_float(result.eta_squared)}, "
        f"omega2={_format_float(result.omega_squared)}; {result.note}"
    )


def format_statistics_result(result: StatisticalAnalysisResult) -> str:
    lines = [
        "Statistical Analysis - Delta %",
        f"Root: {result.root_path or 'N/A'}",
        f"SciPy available: {'yes' if result.scipy_available else 'no'}",
        "",
        "Warnings",
    ]
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")

    lines.extend(["", "Descriptive Statistics"])
    if result.group_statistics:
        lines.extend(_format_descriptive_line(summary) for summary in result.group_statistics)
    else:
        lines.append("No valid groups.")

    lines.extend(
        [
            "",
            "Assumption Checks",
            f"{result.variance_check.method}: statistic={_format_float(result.variance_check.statistic)}, "
            f"p={_format_float(result.variance_check.p_value)}; {result.variance_check.note}",
        ]
    )
    for summary in result.group_statistics:
        lines.append(
            f"{summary.group_name} Shapiro-Wilk: W={_format_float(summary.shapiro_statistic)}, "
            f"p={_format_float(summary.shapiro_p_value)}; {summary.normality_note}"
        )

    lines.extend(["", "One-way ANOVA", _format_anova_line(result.anova)])
    lines.extend(["", "Per-Sample Delta %"])
    if result.samples:
        for sample in result.samples:
            warnings = "; ".join(sample.warnings) if sample.warnings else "None"
            lines.append(
                f"{sample.group_name}/{sample.sample_name}: delta={_format_float(sample.delta_percent)}%, "
                f"baseline={_format_float(sample.baseline)} pF, raw delta={_format_float(sample.delta_capacitance)} pF, "
                f"drop={_format_float(sample.drop_time)}s, warnings={warnings}"
            )
    else:
        lines.append("No valid samples.")

    return "\n".join(lines)


def _rows_for_group_statistics(result: StatisticalAnalysisResult) -> Iterable[list[str]]:
    yield ["Descriptive Statistics"]
    yield [
        "group",
        "n",
        "mean_delta_percent",
        "sd",
        "sem",
        "median",
        "q1",
        "q3",
        "iqr",
        "ci95_low",
        "ci95_high",
        "shapiro_w",
        "shapiro_p",
        "note",
    ]
    for summary in result.group_statistics:
        yield [
            summary.group_name,
            str(summary.n),
            str(summary.mean),
            str(summary.sd),
            str(summary.sem),
            str(summary.median),
            str(summary.q1),
            str(summary.q3),
            str(summary.iqr),
            str(summary.ci95_low),
            str(summary.ci95_high),
            str(summary.shapiro_statistic),
            str(summary.shapiro_p_value),
            summary.normality_note,
        ]


def statistics_result_to_csv_rows(result: StatisticalAnalysisResult) -> list[list[str]]:
    rows: list[list[str]] = [
        ["Statistical Analysis - Delta %"],
        ["root_path", result.root_path],
        ["scipy_available", "yes" if result.scipy_available else "no"],
        [],
        ["Warnings"],
    ]
    if result.warnings:
        rows.extend([[warning] for warning in result.warnings])
    else:
        rows.append(["None"])

    rows.append([])
    rows.extend(_rows_for_group_statistics(result))
    rows.extend(
        [
            [],
            ["Assumption Checks"],
            ["method", "statistic", "p_value", "note"],
            [
                result.variance_check.method,
                str(result.variance_check.statistic),
                str(result.variance_check.p_value),
                result.variance_check.note,
            ],
            [],
            ["One-way ANOVA"],
            ["method", "group_count", "sample_count", "df_num", "df_den", "statistic", "p_value", "eta_squared", "omega_squared", "note"],
            [
                result.anova.method,
                str(result.anova.group_count),
                str(result.anova.sample_count),
                str(result.anova.df_num),
                str(result.anova.df_den),
                str(result.anova.statistic),
                str(result.anova.p_value),
                str(result.anova.eta_squared),
                str(result.anova.omega_squared),
                result.anova.note,
            ],
            [],
            ["Per-Sample Delta %"],
            [
                "group",
                "sample",
                "delta_percent",
                "delta_capacitance",
                "baseline",
                "drop_time",
                "baseline_warning_status",
                "drop_detection_source",
                "warnings",
            ],
        ]
    )
    for sample in result.samples:
        rows.append(
            [
                sample.group_name,
                sample.sample_name,
                str(sample.delta_percent),
                str(sample.delta_capacitance),
                str(sample.baseline),
                str(sample.drop_time),
                sample.baseline_warning_status,
                sample.drop_detection_source,
                "; ".join(sample.warnings),
            ]
        )
    return rows


def write_statistics_csv(result: StatisticalAnalysisResult, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(statistics_result_to_csv_rows(result))
