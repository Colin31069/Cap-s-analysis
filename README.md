# Skin Analysis 工具說明

這個專案是一個桌面 GUI 工具，用來瀏覽實驗資料夾、讀取 `.xlsx` 原始電容資料、偵測 drop 時間，並將結果以不同模式繪圖顯示。

目前提供兩個版本：
- **Python Edition**（`python-app/`）：主要開發版本，功能完整，穩定可用
- **Tauri Edition**（`tauri-app/`）：Rust/Tauri 重寫版，開發中，尚未達到 Python 版功能同等

---

## Python Edition

### 環境需求

- Python 3.11 以上
- 建議在 macOS 使用 Python 3.12 以上，以降低 Tk 介面問題
- 套件需求請參考 `python-app/requirements-gui.txt`

### 安裝方式

#### 一般安裝

```bash
cd python-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-gui.txt
```

#### macOS 建議安裝方式

```bash
cd python-app
chmod +x ./setup_macos_gui_env.sh
./setup_macos_gui_env.sh
source ./.venv-gui/bin/activate
```

如果你在 macOS 遇到下拉選單、勾選框或焦點問題，請另外閱讀 [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md)。

### 啟動方式

```bash
cd python-app
python3 main.py
```

### 資料夾結構

程式會把 `ROOT` 底下的每一個子資料夾視為一組實驗：

```text
ROOT/
  實驗A/
    1.xlsx
    2.xlsx
  實驗B/
    1.xlsx
    2.xlsx
```

每個 Excel 檔案都需要有 `pF - Plot 0` 這個欄位。

### 藥品標記與自動保存

- 左側先貼上或選擇 `Root Path`，再從 `Experiment Folder` 清單選擇目標實驗
- 使用者可以設定本次實驗加入幾種藥品，範圍是 `0` 到 `5`
- 每種藥品都有兩個自由輸入欄位：`Name` 與 `Dose`
- `Medicine Metadata` 預設收合，需要時再展開編輯
- 這些標記會自動保存到該實驗資料夾內的 `.skin_analysis_metadata.json`
- 如果 JSON 不存在，程式會自動建立預設內容
- 如果 JSON 損壞或格式不正確，程式會回到預設 1 列空白欄位並提示使用者

範例：

```json
{
  "medicine_count": 2,
  "medicines": [
    {"name": "lanolin", "dose": "1% 5mL"},
    {"name": "plastik 70", "dose": "1.5uL"}
  ]
}
```

### 使用流程

1. 啟動程式後，在左側 `Root Path` 貼上實驗根目錄，或點選 `Browse...` 選取資料夾。
2. 按下 `Enter` 或 `Refresh List` 重新載入 `Experiment Folder` 清單。
3. 從清單選擇目標 `Experiment Folder`。
4. 視需要展開 `Medicine Metadata`，設定藥品數量並填入每種藥品的名稱與劑量。
5. 視需求選擇顯示模式：
   - `Normalized (%)`：以每個檔案各自 baseline 視窗平均值為 100% 顯示相對變化，時間軸會以偵測到的 drop 作為 `0`
   - `Raw Data (pF)`：顯示原始電容值，時間軸會以偵測到的 drop 作為 `0`
   - `Baseline Only (Raw Baseline Window)`：只顯示本次設定的 baseline 區段，但仍使用相同的相對 drop 時間軸
6. 視需求調整 timing、圖例與視覺選項：
   - `Baseline Duration (s)`：設定前面多少秒拿來做 baseline 平均；只保留在本次程式執行期間，不會寫入 metadata
   - `Drug Apply Time (s)`：設定大約在幾秒附近施加藥品
   - `Apply Window +/- (s)`：設定施藥時間上下各容許多少秒做 drop 搜尋
   - `Baseline Accuracy Threshold (%)`：設定 baseline 品質警示門檻；只用來提示，不會改變 `Normalized (%)` 的 100% 定義，也不會自動排除資料
   - `Overlay Mode`：將不同實驗資料疊加在同一張圖上
   - `Experiment Color`：同一次載入的實驗使用同色，靠線型區分不同 sample
   - `Show Drop Lines`：顯示 `0` 秒位置的垂直輔助線，也就是各條曲線對齊後的 drop 參考點
   - `Legend Customization`：控制圖例是否顯示 baseline、delta；若 baseline 品質可疑，圖例會加上 `注意` 或 `不準確`
7. 點選 `LOAD & PLOT` 載入並繪圖。
8. 如果 baseline 視窗和施藥搜尋區間重疊，程式會自動縮短 baseline 視窗；如果在指定的施藥時間區間內沒有找到明顯反應點，程式會警告後退回自動搜尋。
9. 如果某些檔案的 baseline 視窗尾端偏移過大，或在 baseline 期間就出現連續上升，程式會跳出警示視窗列出受影響的 sample，供使用者自行判斷是否接受這筆實驗資料。
10. 圖表標題會顯示實驗資料夾名稱與藥品標記資訊。
11. 需要輸出圖片時，點選 `Export Plot` 儲存成 `.png`。

### 測試與驗證

```bash
cd python-app
python3 -m unittest discover
python3 -m py_compile main.py skin_analysis/*.py
```

`python-app/tk_macos_smoke_test.py` 是手動 GUI smoke test，可用來檢查 macOS 的 Tk 元件是否正常互動。

---

## Tauri Edition（開發中）

Tauri Edition 是用 Rust + Tauri + Svelte 重寫的跨平台桌面應用，目標是取代 Python Edition 的打包與分發方式，保留相同的分析邏輯與操作流程。

> **目前狀態**：開發中，功能尚未與 Python Edition 同步，不建議用於正式分析。

### 環境需求

- Node.js 18 以上
- Rust（透過 [rustup](https://rustup.rs/) 安裝）
- Tauri CLI（`cargo install tauri-cli`）

### 啟動方式

```bash
cd tauri-app
npm install
npm run tauri dev
```

### 打包

```bash
cd tauri-app
npm run tauri build
```

### 架構說明

| 層 | 技術 |
|----|------|
| 桌面殼層 | Tauri（Rust） |
| 前端 UI | Svelte + TypeScript |
| 繪圖 | Plotly.js |
| 分析核心 | Rust（對應 Python 的 `skin_analysis/`） |

版本間的同步規則請見 [MIGRATION_RULES.md](./MIGRATION_RULES.md)。

---

## 常見問題

### 找不到檔案或資料夾

- 請先確認 `Root Path` 是否正確，並按過 `Enter` 或 `Refresh List`
- 請確認 `ROOT` 底下確實有實驗資料夾
- 請確認目標資料夾中真的有 `.xlsx` 檔案

### Excel 檔案讀不到

- 請確認檔案格式是 `.xlsx`
- 請確認欄位名稱包含 `pF - Plot 0`

### GUI 控制元件無法互動（macOS）

- 先執行 `cd python-app && python3 tk_macos_smoke_test.py`
- 若 smoke test 也有問題，通常是本機 Python/Tk 環境，不是主程式邏輯
- 詳細處理方式請看 [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md)
