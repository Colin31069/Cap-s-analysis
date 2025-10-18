docs: add summary of 20251007 lanolin analysis pipeline

# Lanolin Long-Store vs Fresh Pipeline 數據分析流程說明

## 🎯 目的
比較 **fresh (new)** 與 **long-stored (old)** 兩種保存狀態的 lanolin 薄膜，對 profenofos（兩種濃度：`100x`、`10000x`）滴加後的電容變化動態。最終輸出每個濃度一張對比圖（mean±SEM）與一份對應的 CSV。

---

## 📂 1. 輸入與資料結構

- 資料夾結構：  
  `<ROOT>/<濃度: 100x|10000x>/<批次: new|old>/<rep: 1|2|3>(no|L|F|Final).xlsx`

- 每個 replicate 含三段：  
  - `no.xlsx`：未載膜背景（求 Ci）  
  - `L.xlsx`：成膜穩態  
  - `F.xlsx` 或 `Final.xlsx`：成膜延續＋滴藥反應全程  

---

## ⚙️ 2. 滴藥瞬間偵測

**目標**：找出 F 段中「滴藥瞬間」的索引 `idx_pest`。  

**步驟：**
1. 以 L 的長度 `L_len` 當成 F 的成膜邊界。  
2. L 最後 200 點為基線，計算 `mean`、`std`。  
3. 在 `[L_len, L_len + 300]` 範圍內尋找首個超過 `mean + 3σ` 的點。  
4. 若失敗則以導數門檻 0.003 pF/步 補強。  
5. 仍找不到則使用 `L_len`（保守策略）。  

---

## 📈 3. 單條曲線轉換

函式 `load_and_make_deltaC_series(...)`：  
1. 讀取 `no`, `L`, `F`。  
2. 基線 `Ci = mean(no)`。  
3. 以滴藥瞬間為 0 軸，時間轉為「相對滴藥 (min)」。  
4. 將 F 段轉為 ΔC％：`(C − Ci)/Ci*100`。  
5. 選項：
   - `VISUAL_ZERO_AT_PEST=True` → 顯示上讓 x=0 的 ΔC = 0%。  
   - `PESTICIDE_ZERO_ADJUST_MIN` 可微調 0 軸位置。  
6. 回傳兩欄：`Time_after_pesticide (min)`、`DeltaC (%)`。  

---

## 🧮 4. 多條曲線彙整

函式 `summarize_and_plot(ROOT)`：
1. 處理兩濃度 `100x`, `10000x`。  
2. 每批次 (new/old) 收集最多 3 條 replicate 曲線。  
3. 內插到共用時間軸 `-0.5 → 10 min` (每秒一點)。  
4. Coverage gating：
   - `MIN_TRACES_COUNT=2`
   - `MIN_TRACES_FRACTION=0.7` → 不足則設 NaN。  
5. 計算 mean ± SEM。  
6. 輸出：
   - `analysis_outputs/DeltaC_vs_time_<濃度>.png`
   - `analysis_outputs/DeltaC_mean_sem_<濃度>.csv`  

---

## ⚙️ 5. 可調參數

| 類別 | 名稱 | 說明 |
|------|------|------|
| 偵測 | `BASELINE_TAIL_OF_L` | 基線取樣長度 |
| 偵測 | `SEARCH_AFTER_L` | 搜尋窗口長度 |
| 偵測 | `SIGMA` | σ 門檻倍數 |
| 偵測 | `DERIV_PF_TH` | 導數備援門檻 |
| 對齊 | `PESTICIDE_ZERO_ADJUST_MIN` | 0 軸微調 |
| 顯示 | `VISUAL_ZERO_AT_PEST` | 是否強制 ΔC(0)=0% |
| 時間 | `X_RANGE_MIN / X_RANGE_MAX` | 時間範圍 |
| 統計 | `MIN_TRACES_COUNT / MIN_TRACES_FRACTION` | 平均取樣門檻 |

---

## 🧠 設計理念

- 以 L 段尾端穩定區域為基線，確保滴藥偵測穩定。  
- 使用 ΔC% 相對 Ci，避免絕對偏移。  
- 共用時間軸 + coverage gating 提高 mean/SEM 可比性。  
- 圖上同時顯示 fresh 與 long-stored，以視覺化對比反應差異。

---

## 📤 輸出結果範例

- `DeltaC_vs_time_100x.png`：fresh (藍) vs old (紅) ±SEM 帶狀圖。  
- `DeltaC_mean_sem_100x.csv`：含時間、new_mean/sem、old_mean/sem。

---

© 2025 Lanolin Sensor Analysis Pipeline
