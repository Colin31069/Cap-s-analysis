# CLAUDE.md — Skin Analysis Project

> 本文件是 Claude Code 的專案導覽。核心開發規則請見 [AGENTS.md](./AGENTS.md)，分析演算法細節請見 [ANALYSIS_METHOD.md](./ANALYSIS_METHOD.md)。

---

## 專案速覽

**用途**：處理皮膚電容量測資料（`.xlsx`），偵測藥物施用後的電容下降時間點，計算 delta，並輸出統計圖表。

**兩個並行實作**：
- `Python version/`（主力、已上線）— Tkinter + Matplotlib 桌面 GUI
- `desktop-tauri/`（進行中移植）— Rust + Tauri v2 + Svelte + Plotly.js

**預設作業區**：`Python version/`，除非使用者明確指定 Tauri。

---

## 目錄結構

```
skin/
├── Python version/
│   ├── main.py                  # 薄啟動器，不含業務邏輯
│   ├── skin_analysis/
│   │   ├── config.py            # 常數與預設值
│   │   ├── filesystem.py        # 實驗資料夾探索
│   │   ├── analysis.py          # Excel 載入、下降點偵測、delta 計算
│   │   ├── metadata.py          # .skin_analysis_metadata.json 讀寫
│   │   ├── models.py            # 資料類別 (ProcessedSignal, PlotPayload…)
│   │   ├── plotting.py          # 顯示模式轉換、繪圖 payload 組裝
│   │   ├── statistics.py        # ANOVA、Dixon Q、Shapiro-Wilk
│   │   ├── exclusions.py        # 樣本排除邏輯
│   │   └── gui.py               # Tkinter 主視窗、執行緒交遞
│   └── tests/                   # 非 GUI 模組的單元測試
├── desktop-tauri/               # Rust/Tauri 移植版
├── shared/parity_cases.json     # Python↔Rust 對等測試案例
├── exprimental_data/            # 範例實驗資料集
├── AGENTS.md                    # AI 代理工作規範（必讀）
├── ANALYSIS_METHOD.md           # 訊號分析演算法說明
├── CHANGELOG.md                 # AI 變更紀錄（僅追加）
├── MIGRATION_RULES.md           # Python/Rust 雙版本同步規則
└── MACOS_GUI_FIXES.md           # macOS Tk 執行環境修復指南
```

---

## 資料格式

```
ROOT/
  Experiment A/
    1.xlsx          ← 必須含欄位 "pF - Plot 0"
    2.xlsx
    .skin_analysis_metadata.json
  Experiment B/
    ...
```

- 基線期：前 20 秒（`BASELINE_DURATION_S = 20`）
- 施藥時間點：25 秒（`DRUG_APPLY_TIME_S = 25`）
- 搜尋容差：±5 秒

---

## 重要常數（`config.py`）

| 常數 | 值 | 說明 |
|---|---|---|
| `BASELINE_DURATION_S` | 20 | 基線計算秒數 |
| `DRUG_APPLY_TIME_S` | 25 | 施藥時間點 |
| `DROP_SEARCH_TOLERANCE_S` | 5 | 下降偵測搜尋容差 |

---

## 快速指令

```bash
# 執行所有單元測試
cd "Python version"
python3 -m unittest discover

# 語法檢查
python3 -m py_compile main.py skin_analysis/*.py

# 啟動 GUI
python3 main.py
```

---

## 執行緒規則（重要）

- 後台 Worker 只做：讀檔、組裝 `PlotPayload`
- Tk widget 更新**必須**在主執行緒，使用 `self.after(...)` 交遞
- **絕對不可**在 Worker 執行緒直接呼叫 Tk 或 Matplotlib widget 方法

---

## 安全擴充點

| 要新增什麼 | 在哪裡改 |
|---|---|
| 新顯示模式 | `plotting.py` |
| 下降偵測行為 | `analysis.py` |
| Metadata 欄位 | `metadata.py`（含向下相容） |
| 新 GUI 控制項 | `gui.py` + 對應 `models.py` |
| 新統計方法 | `statistics.py` |
| 新測試 | `tests/` |

---

## 不可破壞的假設

1. `main.py` 保持為薄啟動器
2. Worker 執行緒不呼叫 Tk/Matplotlib
3. 使用者可見的流程變更須同步更新 `README.md`
4. Metadata schema 變更必須考量磁碟上已存在的 `.json` 檔

---

## Git 分支模型

| 分支 | 用途 |
|---|---|
| `main` | 穩定版 |
| `beta` | 整合測試 |
| `feature/*` | 新功能 |
| `fix/*` | 錯誤修復 |
| `hotfix/*` | 緊急上線修復 |

提交格式：`[feat]` / `[fix]` / `[refactor]` / `[docs]` / `[test]`

---

## Changelog 規則

任何修改 repo 檔案的 AI 代理，完成前必須在 `CHANGELOG.md` 追加一筆紀錄，包含：
- Asia/Taipei 時間戳記
- 簡短摘要
- 受影響的檔案
- 驗證指令或結果
