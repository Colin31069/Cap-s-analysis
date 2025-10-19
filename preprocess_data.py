# preprocess_data.py
# -*- coding: utf-8 -*-
"""
Lanolin Concentration Calibration Curve Analysis Pipeline (v3.1 - Preprocessing with Percentage Change)
- Processes raw data from the specified folder structure.
- For each experimental condition, calculates the mean time-response curve 
  (ΔC % vs. Time) and its corresponding Standard Error of the Mean (SEM).
- Serializes and saves all processed curves into a single 'preprocessed_data.pkl' file 
  for fast loading by the interactive GUI.
"""

import os
import glob
import pickle
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import warnings

# =============================== 1. 設定區 (可調參數) =======================================
# --- 資料夾與檔案結構 ---
ROOT = r"E:\Onedrive\桌面\新增資料夾\1019_lanolin\concetration" # 你的資料根目錄
LANOLIN_CONCS = ["1%", "2.5%", "5%"]
PROFENOFOS_DILUTIONS = ["DI water", "100x", "1000x", "2000x", "10000x"]
REPLICATES = ["1", "2", "3", "4"]

# --- 數據欄位與時間參數 ---
DATA_COL = "pF - Plot 0"
DT_SEC = 0.1
SEC_PER_MIN = 60.0
IDX_PER_MIN = int(SEC_PER_MIN / DT_SEC)

# --- 核心演算法參數 ---
DROP_SEARCH_WINDOW = 100
DROP_SIGMA_THRESHOLD = 3.0
BASELINE_TAIL_FOR_DROP = 100

# --- 輸出設定 ---
OUT_DIR = os.path.join(ROOT, "analysis_outputs_interactive")
os.makedirs(OUT_DIR, exist_ok=True)
OUTPUT_PICKLE_NAME = "preprocessed_data.pkl"

# --- 標準化時間軸設定 (分鐘) ---
TIME_PLOT_X_MIN = -1.0
TIME_PLOT_X_MAX = 5.0 # 擴展時間以供更全面的觀察
COMMON_T_STEP_MIN = 1.0 / 60.0 # ~1秒一個點
COMMON_T = np.arange(TIME_PLOT_X_MIN, TIME_PLOT_X_MAX + 1e-9, COMMON_T_STEP_MIN)

# ============================ 2. 小工具函式 ==========================================
def read_xlsx(path: str) -> Optional[pd.DataFrame]:
    """安全地讀取 Excel，只保留數據欄位，並提供詳細的錯誤報告"""
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_excel(path, engine="openpyxl")
        if DATA_COL not in df.columns:
            warnings.warn(f"'{DATA_COL}' column not found in '{os.path.basename(path)}'. Available columns are: {list(df.columns)}")
            return None
        return df[[DATA_COL]].copy()
    except Exception as e:
        warnings.warn(f"An unexpected error occurred while reading '{os.path.basename(path)}': {e}")
        return None

def mean_sem_2d(arr2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """計算2D陣列的逐欄平均與SEM，忽略NaN"""
    mean = np.nanmean(arr2d, axis=0)
    n = np.sum(np.isfinite(arr2d), axis=0)
    std = np.nanstd(arr2d, axis=0, ddof=1)
    sem = np.divide(std, np.sqrt(n), out=np.full_like(std, np.nan), where=n > 1)
    return mean, sem

def safe_interp(x_new: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """安全的1D內插函式，處理NaN和重複值"""
    m = np.isfinite(x) & np.isfinite(y)
    if not np.any(m): return np.full_like(x_new, np.nan, dtype=float)
    x, y = np.asarray(x[m], float), np.asarray(y[m], float)
    order = np.argsort(x); x, y = x[order], y[order]
    xu, idx = np.unique(x, return_index=True); yu = y[idx]
    return np.interp(x_new, xu, yu, left=np.nan, right=np.nan)

# ============================ 3. 核心計算函式 ==========================
def process_single_replicate_for_timeseries(xi_path: str, xf_path: str) -> Optional[pd.DataFrame]:
    """
    處理單一重複實驗，回傳對齊後的時間序列 DataFrame (Time_min, Delta_C_percent)
    """
    df_i = read_xlsx(xi_path)
    df_f = read_xlsx(xf_path)

    if df_i is None or df_f is None or df_i.empty or df_f.empty:
        return None

    Ci = float(df_i[DATA_COL].mean())
    
    # 【修改 1】: 增加分母保護，如果基線電容Ci接近於0，則無法計算百分比，跳過此數據
    if abs(Ci) < 1e-9:
        warnings.warn(f"Baseline capacitance (Ci) is near zero in '{os.path.basename(xi_path)}'. Cannot calculate percentage change. Skipping replicate.")
        return None
        
    len_i = len(df_i)
    f_data = df_f[DATA_COL].to_numpy()

    s = max(0, len_i - BASELINE_TAIL_FOR_DROP)
    base = df_i[DATA_COL].iloc[s:].to_numpy()
    base = base[np.isfinite(base)]
    if base.size < 10: 
        warnings.warn(f"Baseline in {xi_path} is too short to process.")
        return None
        
    mu, sd = np.mean(base), np.std(base, ddof=1)
    thr = mu + DROP_SIGMA_THRESHOLD * (sd if sd > 1e-9 else 1e-9)
    search_end = min(len_i + DROP_SEARCH_WINDOW, len(f_data))
    over_threshold_indices = np.where(f_data[len_i:search_end] > thr)[0]
    
    idx_drop = len_i + over_threshold_indices[0] if over_threshold_indices.size > 0 else len_i

    time_indices = np.arange(len(f_data))
    time_min = (time_indices - idx_drop) * DT_SEC / SEC_PER_MIN
    
    # 【修改 2】: 更新計算公式為百分比變化
    delta_C_percent_t = (f_data - Ci) / Ci * 100.0
    
    # 【修改 3】: 更新 DataFrame 的欄位名稱
    return pd.DataFrame({"Time_min": time_min, "Delta_C_percent": delta_C_percent_t})

# ============================ 4. 主流程 ==============================
def run_preprocessing(root_dir: str):
    """
    遍歷所有實驗條件，計算平均時間響應曲線和SEM，並將結果儲存到 pickle 檔案中。
    """
    preprocessed_data = {}
    print("Starting data preprocessing...")

    for lanolin_conc in LANOLIN_CONCS:
        for prof_dilution in PROFENOFOS_DILUTIONS:
            print(f"- Processing: {lanolin_conc} / {prof_dilution}")
            
            timeseries_replicates = []
            
            for rep in REPLICATES:
                xi_path = os.path.join(root_dir, prof_dilution, lanolin_conc, f"{rep}i.xlsx")
                xf_path = os.path.join(root_dir, prof_dilution, lanolin_conc, f"{rep}f.xlsx")

                ts_df = process_single_replicate_for_timeseries(xi_path, xf_path)
                if ts_df is not None:
                    timeseries_replicates.append(ts_df)

            if not timeseries_replicates:
                print(f"  - No valid time-series data found for this condition.")
                continue
            
            # --- 內插到共同時間軸並計算 Mean 和 SEM ---
            interp_rows = []
            for df in timeseries_replicates:
                x = df["Time_min"].to_numpy()
                # 【修改 4】: 確認使用新的欄位名稱來獲取Y軸數據
                y = df["Delta_C_percent"].to_numpy()
                interp_rows.append(safe_interp(COMMON_T, x, y))
            
            if not interp_rows:
                print(f"  - Interpolation failed for all replicates.")
                continue
                
            interp_matrix = np.vstack(interp_rows)
            mean_curve, sem_curve = mean_sem_2d(interp_matrix)
            
            # --- 儲存結果到字典 ---
            condition_key = (lanolin_conc, prof_dilution)
            preprocessed_data[condition_key] = {
                'time': COMMON_T,
                'mean': mean_curve,
                'sem': sem_curve
            }
            print(f"  - Processed and stored {len(timeseries_replicates)} replicates.")

    if not preprocessed_data:
        print("\nNo data was processed. Preprocessed file will not be created.")
        return

    # --- 序列化並儲存字典 ---
    pickle_path = os.path.join(OUT_DIR, OUTPUT_PICKLE_NAME)
    try:
        with open(pickle_path, 'wb') as f:
            pickle.dump(preprocessed_data, f)
        print(f"\n✅ Preprocessing complete. Data saved to: {pickle_path}")
    except Exception as e:
        print(f"\n❌ Error saving preprocessed data: {e}")


if __name__ == "__main__":
    run_preprocessing(ROOT)