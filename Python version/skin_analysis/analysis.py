from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_COL, DROP_SIGMA_THRESHOLD, DT_SEC, INITIAL_BASELINE_POINTS
from .models import ProcessedSignal


def read_xlsx_single(path: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception:
        return None

    if DATA_COL not in df.columns:
        return None
    return df[[DATA_COL]].copy()


def analyze_signal(data: np.ndarray) -> ProcessedSignal | None:
    samples = np.asarray(data, dtype=float)
    if samples.size == 0:
        return None

    baseline_len = min(len(samples), INITIAL_BASELINE_POINTS)
    baseline_segment = samples[:baseline_len]
    initial_avg = float(np.mean(baseline_segment))
    sample_std = float(np.std(baseline_segment, ddof=1)) if baseline_len > 1 else 0.0

    threshold = initial_avg + DROP_SIGMA_THRESHOLD * max(sample_std, 1e-4)
    search_end = min(len(samples), baseline_len + 500)
    search_range = samples[baseline_len:search_end]

    over_idx = np.where(search_range > threshold)[0]
    idx_drop = baseline_len + (int(over_idx[0]) if over_idx.size > 0 else 0)

    final_avg = float(np.nanmean(samples[-100:])) if len(samples) >= 100 else float("nan")
    delta_raw = final_avg - initial_avg if not np.isnan(final_avg) else float("nan")

    return ProcessedSignal(
        time_sec=np.arange(len(samples), dtype=float) * DT_SEC,
        capacitance=samples,
        drop_time=idx_drop * DT_SEC,
        delta_capacitance=delta_raw,
        initial_avg=initial_avg,
    )


def process_single_file(file_path: str) -> ProcessedSignal | None:
    df = read_xlsx_single(file_path)
    if df is None or df.empty:
        return None
    return analyze_signal(df[DATA_COL].to_numpy())
