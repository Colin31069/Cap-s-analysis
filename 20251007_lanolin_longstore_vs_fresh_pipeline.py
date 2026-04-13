# -*- coding: utf-8 -*-
"""
Lanolin (fresh vs long-stored) analysis pipeline
- 自動讀取資料夾結構：<ROOT>/(100x|10000x)/(new|old)/(1|2|3)(no|L|F|Final).xlsx
- 從 L 的長度推回 F 中 L 段的長度，於 [L_end, L_end+300] 內偵測滴藥瞬間
- 以 Ci = mean(no.xlsx) 為基準，輸出 ΔC(%) = (C - Ci)/Ci * 100
- x 軸對齊「滴藥瞬間 = 0 min」
- 產出 mean ± SEM 疊圖：各濃度各一張圖（fresh vs long-stored）
"""

import os, glob, math
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



# =============================== 設定區 =======================================
ROOT = r"E:\Onedrive\project\projecting\skin\實驗資料\實驗分析\20251007\data\1004_lanolin\storage"  # 你的資料根目錄（照 tree.txt 結構）
CONCENTRATIONS = ["100x", "10000x"]
BATCHES = ["new", "old"]               # fresh vs long-stored
REPLICATES = ["1", "2", "3"]           # 1/2/3 組
TIME_COL = "Time - Plot 0"
PF_COL = "pF - Plot 0"

# 取樣：1 單元格 = 0.1 秒
DT_SEC = 0.1
SEC_PER_MIN = 60.0
IDX_PER_MIN = int(SEC_PER_MIN / DT_SEC)   # 600

# 滴藥偵測設定（從 L 結尾向後 300 格內）
SEARCH_AFTER_L = 300
BASELINE_TAIL_OF_L = 200                 # 用 L 的最後 200 格當基線
SIGMA = 3.0                              # 3σ 門檻
DERIV_PF_TH = 0.003                      # 微分備援門檻（pF/step），遇到平台時好用

# 顯示滴藥前 0.5 分鐘 + 滴藥後 10 分鐘
X_RANGE_MIN = -0.5
X_RANGE_MAX = 10.0
X_STEP_MIN  = 1.0 / 60.0
COMMON_T = np.arange(X_RANGE_MIN, X_RANGE_MAX + 1e-9, X_STEP_MIN)

# 視覺：是否讓曲線在 x=0 從 0% 開始（只做直流偏移）
VISUAL_ZERO_AT_PEST = True


OUT_DIR = os.path.join(ROOT, "analysis_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

COLORS = {"new": "#1f77b4", "old": "#d62728"}  # fresh=藍, old=紅

# 全域時間微調 (正值 = 向右移，單位：分鐘)
PESTICIDE_ZERO_ADJUST_MIN = 0.0   # 例如延後 0.20 min ≈ 12 秒


# ============================ 小工具 ==========================================
def read_xlsx(path: str) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_excel(path, engine="openpyxl")
        if TIME_COL not in df.columns or PF_COL not in df.columns:
            return None
        return df[[TIME_COL, PF_COL]].copy()
    except Exception:
        return None

def mean_sem(arr2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """沿 axis=0（多條 trace）計算 mean 與 SEM，忽略 NaN"""
    mean = np.nanmean(arr2d, axis=0)
    # 有效樣本數
    n = np.sum(np.isfinite(arr2d), axis=0)
    std = np.nanstd(arr2d, axis=0, ddof=1)
    sem = np.divide(std, np.sqrt(n), out=np.full_like(std, np.nan), where=n > 1)
    return mean, sem

def safe_interp(x_new: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    m = np.isfinite(x) & np.isfinite(y)
    if not np.any(m): 
        return np.full_like(x_new, np.nan, dtype=float)
    x = np.asarray(x[m], float); y = np.asarray(y[m], float)
    order = np.argsort(x); x = x[order]; y = y[order]
    xu, idx = np.unique(x, return_index=True)
    yu = y[idx]
    return np.interp(x_new, xu, yu, left=np.nan, right=np.nan)

def last_valid_index(arr: np.ndarray) -> int:
    """回傳最後一個有效（finite 且 非 0）的索引；若全無，回傳 -1"""
    v = np.isfinite(arr) & (arr != 0)
    idx = np.where(v)[0]
    return int(idx[-1]) if idx.size > 0 else -1


# ============================ 滴藥偵測 ========================================
def detect_pesticide_index(F_pf: np.ndarray, L_len: int) -> Optional[int]:
    """
    在 F 序列中，已知前 L_len 是成膜穩態延續。
    於 [L_len, L_len+SEARCH_AFTER_L] 範圍內找滴藥瞬間：
      - 基於 L 尾端 BASELINE_TAIL_OF_L 的 mean/std 做 3σ 門檻
      - 備援：一階差分門檻（避免平台）
    回傳：F 中的索引（int）
    """
    n = len(F_pf)
    if L_len <= 0 or L_len >= n:
        return None

    s = max(0, L_len - BASELINE_TAIL_OF_L)
    e = L_len
    base = F_pf[s:e]
    base = base[np.isfinite(base)]
    if base.size < 10:
        return None

    mu = float(np.mean(base))
    sd = float(np.std(base, ddof=1))
    thr = mu + SIGMA * (sd if sd > 1e-12 else 1e-12)

    end = min(L_len + SEARCH_AFTER_L, n - 1)
    # 先看幅度門檻
    for i in range(L_len, end + 1):
        if F_pf[i] >= thr:
            return i

    # 備援：看導數
    d = np.diff(F_pf.astype(float), prepend=F_pf[0])
    for i in range(L_len, end + 1):
        if d[i] >= DERIV_PF_TH:
            return i

    # 若仍找不到，回傳 L_len（把 L 結束當作滴藥點）
    return L_len

# =========================== 個體 trace 建構 ==================================
def build_trace_paths(root: str, conc: str, batch: str, rep: str) -> Dict[str, str]:
    folder = os.path.join(root, conc, batch)
    # 允許 F 檔名為 F 或 Final
    patterns = {
        "no": os.path.join(folder, f"{rep}no.xlsx"),
        "L":  os.path.join(folder, f"{rep}L.xlsx"),
        "F":  os.path.join(folder, f"{rep}F.xlsx"),
        "Final": os.path.join(folder, f"{rep}Final.xlsx"),
    }
    return patterns

def load_and_make_deltaC_series(paths: Dict[str, str]) -> Optional[pd.DataFrame]:
    """
    載入單一 replicate 的 no/L/F：
      1) 以 L 的長度界定 F 前段為成膜穩態
      2) 在 [L_end, L_end+SEARCH_AFTER_L] 偵測「滴藥瞬間」
      3) 取出「滴藥前 X_RANGE_MIN（負值）～ 滴藥後 X_RANGE_MAX」的片段
      4) 計算 ΔC(%) = (C - Ci)/Ci*100，並可視覺上讓 x=0 從 0% 開始
      5) 回傳欄位：
         - Time_after_pesticide (min)  # 含負時間（成膜穩態）
         - DeltaC (%)
    """
    p_no = paths["no"]; p_L = paths["L"]
    p_F  = paths["F"] if os.path.exists(paths["F"]) else paths["Final"]

    if not (os.path.exists(p_no) and os.path.exists(p_L) and os.path.exists(p_F)):
        return None

    df_no = read_xlsx(p_no); df_L = read_xlsx(p_L); df_F = read_xlsx(p_F)
    if df_no is None or df_L is None or df_F is None:
        return None

    # 基線：Ci 為 no.xlsx 的整段平均
    Ci = float(np.mean(pd.to_numeric(df_no[PF_COL], errors="coerce")))

    # L 的長度（格數，0.1s 一格）
    L_len = len(df_L)

    # F 的 pF 時序（F 前 L_len 與 L 一致）
    F_pf = pd.to_numeric(df_F[PF_COL], errors="coerce").to_numpy()

    # 1) 偵測滴藥瞬間（回傳 F 中索引）
    idx_pest = detect_pesticide_index(F_pf, L_len=L_len)
    if idx_pest is None:
        return None

    # 2) 片段邊界：包含滴藥前 |X_RANGE_MIN| 分鐘（不得超過 L 長度）
    pre_needed_steps  = int(abs(X_RANGE_MIN) * SEC_PER_MIN / DT_SEC) if X_RANGE_MIN < 0 else 0
    pre_steps         = min(pre_needed_steps, L_len, idx_pest)  # 保險：不得超過可用長度
    start             = max(0, idx_pest - pre_steps)

    # 右側最多 X_RANGE_MAX 分鐘，且不得超過最後有效資料（排除 NaN/0）
    valid_end         = last_valid_index(F_pf)
    if valid_end < 0:     # 全部無效
        return None
    post_needed_steps = int(X_RANGE_MAX * SEC_PER_MIN / DT_SEC)
    stop              = min(idx_pest + post_needed_steps, valid_end + 1)

    if stop <= start:
        return None

    # 3) 擷取片段
    pf_seg = F_pf[start:stop]

    # 4) 建立時間軸（以滴藥點為 0；可加全域微調）
    idx   = np.arange(start, stop)
    t_min = (idx - idx_pest) * DT_SEC / SEC_PER_MIN + PESTICIDE_ZERO_ADJUST_MIN

    # 5) ΔC(%) 相對 Ci
    deltaC_percent = (pf_seg - Ci) / Ci * 100.0

    # （選項）視覺歸零：讓圖上 x=0 的值為 0%，不改物理定義
    if 'VISUAL_ZERO_AT_PEST' in globals() and VISUAL_ZERO_AT_PEST:
        zero_idx = int(np.argmin(np.abs(t_min - 0.0)))
        if 0 <= zero_idx < len(deltaC_percent) and np.isfinite(deltaC_percent[zero_idx]):
            deltaC0 = float(deltaC_percent[zero_idx])
            deltaC_percent = deltaC_percent - deltaC0

    return pd.DataFrame({
        "Time_after_pesticide (min)": t_min,
        "DeltaC (%)": deltaC_percent
    })


# ============================== 主流程 ========================================


def collect_group_traces(root: str, conc: str, batch: str) -> List[pd.DataFrame]:
    traces = []
    for rep in REPLICATES:
        paths = build_trace_paths(root, conc, batch, rep)
        df = load_and_make_deltaC_series(paths)
        if df is not None and len(df) > 5:
            traces.append(df)
    return traces

def summarize_and_plot(root: str):
    for conc in CONCENTRATIONS:
        group_series = {}
        interp_matrix = {}

        for batch in BATCHES:
            traces = collect_group_traces(root, conc, batch)
            group_series[batch] = traces

            rows = []
            for df in traces:
                x = df["Time_after_pesticide (min)"].to_numpy()
                y = df["DeltaC (%)"].to_numpy()
                rows.append(safe_interp(COMMON_T, x, y))
            interp_matrix[batch] = np.vstack(rows) if rows else np.full((0, len(COMMON_T)), np.nan)

        # --- 畫圖（fresh vs long-stored） ---
        fig, ax = plt.subplots(figsize=(12, 7))

        # coverage gating 設定
        MIN_TRACES_COUNT = 2
        MIN_TRACES_FRACTION = 0.7

        out_df = pd.DataFrame({"Time (min)": COMMON_T})

        for batch in BATCHES:
            M = interp_matrix[batch]
            if M.shape[0] == 0:
                continue

            # coverage gating：有效樣本不足的時間點設為 NaN
            valid_n = np.sum(np.isfinite(M), axis=0)
            min_required = max(MIN_TRACES_COUNT,
                               int(np.ceil(MIN_TRACES_FRACTION * M.shape[0])))
            good = valid_n >= min_required
            M = M.copy()
            M[:, ~good] = np.nan

            mean, sem = mean_sem(M)

            # 更穩的填色（避開 NaN 連線）
            import numpy.ma as ma
            y  = ma.masked_invalid(mean)
            y0 = ma.masked_invalid(mean - sem)
            y1 = ma.masked_invalid(mean + sem)

            ax.plot(COMMON_T, y, color=COLORS[batch], linewidth=2.2, label=batch)
            ax.fill_between(COMMON_T, y0, y1, where=~y.mask, color=COLORS[batch], alpha=0.2)

            out_df[f"{batch}_mean"] = mean
            out_df[f"{batch}_sem"]  = sem

        ax.set_xlim(X_RANGE_MIN, X_RANGE_MAX)
        ax.set_xlabel("Time after Pesticide (min)", fontsize=13)
        ax.set_ylabel("Capacitance Change (%)", fontsize=13)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(title=f"{conc}: fresh(new) vs long-stored(old)")
        ax.set_xlim(X_RANGE_MIN, X_RANGE_MAX)
        ax.axvline(0.0, color='gray', linestyle='--', linewidth=1)  # 標示 Pesticide
        ax.set_xlabel("Time relative to Pesticide (min)", fontsize=13)

        out_png = os.path.join(OUT_DIR, f"DeltaC_vs_time_{conc}.png")
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        print(f"✅ Saved: {out_png}")
        plt.close()

        out_csv = os.path.join(OUT_DIR, f"DeltaC_mean_sem_{conc}.csv")
        out_df.to_csv(out_csv, index=False)
        print(f"📄 Saved: {out_csv}")


        # --- 匯出彙總（可選） ---
        # 平均曲線另存 CSV（方便後續報告排版）
        out_csv = os.path.join(OUT_DIR, f"DeltaC_mean_sem_{conc}.csv")
        out_df = pd.DataFrame({"Time (min)": COMMON_T})
        for batch in BATCHES:
            M = interp_matrix[batch]
            if M.shape[0] == 0:
                out_df[f"{batch}_mean"] = np.nan
                out_df[f"{batch}_sem"] = np.nan
            else:
                mean, sem = mean_sem(M)
                out_df[f"{batch}_mean"] = mean
                out_df[f"{batch}_sem"] = sem
        out_df.to_csv(out_csv, index=False)
        print(f"📄 Saved: {out_csv}")
    


if __name__ == "__main__":
    summarize_and_plot(ROOT)
