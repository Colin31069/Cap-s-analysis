# Skin Analysis 工具說明

這個專案是一個用 `Tkinter` 與 `Matplotlib` 製作的桌面 GUI 工具，用來瀏覽實驗資料夾、讀取 `.xlsx` 原始電容資料、偵測 drop 時間，並將結果以不同模式繪圖顯示。

## 環境需求

- Python 3.11 以上
- 建議在 macOS 使用 Python 3.12 以上，以降低 Tk 介面問題
- Python 版本的程式碼放在 `Python version/`，請先 `cd` 進去再執行
- 套件需求請參考 `Python version/requirements-gui.txt`
- 統計檢定需要 `scipy`；若未安裝，程式仍可顯示描述統計與 ANOVA 的 F 值，但 p-value、95% CI 等推論統計會標示為不可用

## 安裝方式

### 一般安裝

```bash
cd "Python version"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-gui.txt
```

### macOS 建議安裝方式

```bash
cd "Python version"
chmod +x ./setup_macos_gui_env.sh
./setup_macos_gui_env.sh
source ./.venv-gui/bin/activate
```

macOS 15 以上請使用 Python 3.12 或 3.13 建立 GUI 環境；Python 3.11 的 Tk runtime 可能在開啟視窗前直接觸發 macOS crash report。

如果使用 Homebrew Python 3.13，請先確認有安裝 Tk：

```bash
brew install python-tk@3.13
```

如果你在 macOS 遇到下拉選單、勾選框或焦點問題，請另外閱讀 [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md)。

## 啟動方式

```bash
cd "Python version"
python3 main.py
```

如果已建立 macOS GUI 環境，`python3 main.py` 會在偵測到全域 NumPy/Matplotlib ABI 不相容時，自動改用 `./.venv-gui/bin/python` 重新啟動。也可以直接使用：

```bash
cd "Python version"
./.venv-gui/bin/python main.py
```

## 資料夾結構

程式現在會把 `ROOT` 底下的每一個子資料夾視為一組實驗：

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

## 藥品標記與自動保存

- 左側先貼上或選擇 `Root Path`，再從 `Experiment Folder` 清單選擇目標實驗
- 使用者可以設定本次實驗加入幾種藥品，範圍是 `0` 到 `5`
- 每種藥品都有兩個自由輸入欄位：`Name` 與 `Dose`
- `Medicine Metadata` 預設收合，需要時再展開編輯
- 藥品標記與手動 sample 排除清單會自動保存到該實驗資料夾內的 `.skin_analysis_metadata.json`
- 如果 JSON 不存在，程式會自動建立預設內容
- 如果 JSON 損壞或格式不正確，程式會回到預設 1 列空白欄位並提示使用者

範例：

```json
{
  "medicine_count": 2,
  "medicines": [
    {"name": "lanolin", "dose": "1% 5mL"},
    {"name": "plastik 70", "dose": "1.5uL"}
  ],
  "excluded_samples": [
    {"file_name": "3.xlsx", "reason": "baseline drift"},
    {"file_name": "4.xlsx", "reason": "Dixon Q10 alpha=0.05", "method": "dixon_q"}
  ]
}
```

## 使用流程

1. 啟動程式後，在左側 `Root Path` 貼上實驗根目錄，或點選 `Browse...` 選取資料夾。
2. 按下 `Enter` 或 `Refresh List` 重新載入 `Experiment Folder` 清單。
3. 從清單選擇目標 `Experiment Folder`。
4. 視需要展開 `Medicine Metadata`，設定藥品數量並填入每種藥品的名稱與劑量。
5. 視需要在 `Sample Exclusion` 選擇要踢除的 `.xlsx` sample，按 `Exclude Selected` 並輸入可選原因；按 `Restore Selected` 可恢復納入分析。
6. 視需求選擇顯示模式：
   - `Normalized (%)`：以每個檔案各自 baseline 視窗平均值為 100% 顯示相對變化，時間軸會以偵測到的 drop 作為 `0`
   - `Raw Data (pF)`：顯示原始電容值，時間軸會以偵測到的 drop 作為 `0`
   - `Baseline Only (Raw Baseline Window)`：只顯示本次設定的 baseline 區段，但仍使用相同的相對 drop 時間軸
7. 視需求調整 timing、圖例與視覺選項：
   - `Plot Title (optional)`：可自訂本次繪圖標題；留空時維持預設標題，也就是實驗資料夾名稱與藥品標記資訊。已繪出的圖會在編輯時立即更新，匯出圖片也會使用目前畫面上的標題
   - `Sample Exclusion`：手動排除明確有問題的 sample，不會刪除原始 `.xlsx`。規則是 `n < 5` 禁止排除；`n >= 5` 最多可排除 `floor(n / 5)` 筆，例如 `n=5-9` 最多 1 筆、`n=10-14` 最多 2 筆
   - `Baseline Duration (s)`：設定前面多少秒拿來做 baseline 平均；只保留在本次程式執行期間，不會寫入 metadata
   - `Drug Apply Time (s)`：設定大約在幾秒附近施加藥品
   - `Apply Window +/- (s)`：設定施藥時間上下各容許多少秒做 drop 搜尋
   - `Baseline Accuracy Threshold (%)`：設定 baseline 品質警示門檻；只用來提示，不會改變 `Normalized (%)` 的 100% 定義，也不會自動排除資料
   - `Overlay Mode`：將不同實驗資料疊加在同一張圖上
   - `Experiment Color`：同一次載入的實驗使用同色，靠線型區分不同 sample
   - `Show Drop Lines`：顯示 `0` 秒位置的垂直輔助線，也就是各條曲線對齊後的 drop 參考點
   - `Legend Customization`：控制圖例是否顯示 baseline、delta；疊圖且開啟 `Experiment Color` 時，圖例只會以放大的色塊列出每個藥品/濃度組別，沒有填 metadata 時會改用實驗資料夾名稱；baseline 品質可疑時仍會跳出警示視窗
8. 點選 `LOAD & PLOT` 載入並繪圖。
9. 如果 baseline 視窗和施藥搜尋區間重疊，程式會自動縮短 baseline 視窗；如果在指定的施藥時間區間內沒有找到明顯反應點，程式會警告後退回自動搜尋。
10. 如果某些檔案的 baseline 視窗尾端偏移過大，或在 baseline 期間就出現連續上升，程式會跳出警示視窗列出受影響的 sample，供使用者自行判斷是否接受這筆實驗資料。
11. 圖表標題會使用 `Plot Title (optional)` 的內容；若留空，會顯示實驗資料夾名稱與藥品標記資訊。
12. 需要輸出圖片時，點選 `Export Plot` 儲存成 `.png`。

## 手動踢除 sample

`Sample Exclusion` 是人工資料品質決策，不是自動 outlier detection。被踢除的 `.xlsx` 不會被刪除，只會在目前工具的繪圖、`Delta %` 統計、ANOVA 與 CSV 匯出中排除；metadata 會保留檔名與原因。

`Run Dixon Q` 會檢查目前選取的 experiment folder，使用 Dixon's Q `Q10` test 針對組內 `Delta %` 的最低端或最高端提出一筆建議剔除。它只會選中建議 sample 並預填理由，不會自動排除；確認後仍需按 `Exclude Selected` 才會寫入 metadata。一般規則仍是 `n < 5` 禁止排除，但若 `n=3` 或 `n=4` 且 Dixon Q 在 `α=0.05` 通過，工具允許排除一筆 Dixon-backed sample。

統計視窗會另外提供 `Outlier Review`，用組內 `Delta %` 的 leave-one-out median/MAD 與 modified z-score 標記候選樣本。這只是提醒，不會自動排除；使用者仍應回到原始曲線、baseline/timing warning 與實驗紀錄確認後，再用 `Sample Exclusion` 手動處理。

此工具採用固定上限作為保護欄：

```text
n < 5: 0
n >= 5: floor(n / 5)
```

例如 `n=10` 最多可踢除 2 筆。這個設計是為了符合實驗紀錄習慣：排除標準應預先定義、逐組回報排除資料與實際 n，而不是事後任意移除。參考：[ARRIVE inclusion/exclusion criteria](https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3a/explanation)、[ARRIVE reporting exclusions](https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3b/explanation)、[ARRIVE exact n](https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3c/explanation)、[GraphPad outlier guide](https://www.graphpad.com/guides/prism/8/statistics/stat_how_to_removing_outliers.htm)、[GraphPad ROUT method](https://www.graphpad.com/guides/prism/latest/statistics/stat_how_it_works_rout_method.htm)、[NIST generalized ESD](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h3.htm)。

## 統計分析

點選左側 `Statistics` 可針對目前 `Root Path` 底下所有直接子資料夾進行統計分析。這個功能把每個子資料夾視為一個濃度組，資料夾名稱就是濃度標籤；每個 `.xlsx` 檔案視為一片獨立電極片。

目前主要 endpoint 是 `Delta %`：

```text
Delta % = raw delta pF / 該電極片自己的 baseline pF * 100
```

統計視窗會直接對所有濃度組執行 one-way ANOVA，並輸出：

- 每個濃度組的 `n`、mean、SD、SEM、median、IQR、95% CI
- 每組被手動踢除的 sample 檔名與原因；描述統計中的 `n` 是排除後納入分析的數量
- one-way ANOVA 的 F 值、自由度與 p-value
- ANOVA effect size：eta-squared 與 omega-squared
- Shapiro-Wilk normality check 與 Brown-Forsythe variance check
- Dixon Q review：對每組納入分析後 `n=3-10` 的 `Delta %` 執行 Q10 test，若 `Q > Qcritical` 則列為 `Recommended Dixon Exclusions`
- ANOVA sensitivity：預覽若移除 Dixon 建議剔除樣本後，one-way ANOVA 會如何變化；這只是報告預覽，不會自動改 metadata
- robust outlier review：只在每組納入分析後 `n >= 5` 時，使用組內 leave-one-out median/MAD 與 `abs(modified z) >= 3.5` 標記 `Delta %` 候選 outlier；候選不會自動排除
- 每片電極片的 Delta % 明細與資料品質警示

結果可以從統計視窗匯出為 `.csv`。如果某組樣本數太少，例如 `n < 2` 或 `n < 3`，視窗會列出警示並略過不適合的推論檢定。這版只包含 one-way ANOVA，不包含兩兩比較或事後比較。

---

## Tauri 版本 (desktop-tauri/)

`desktop-tauri/` 是以 Rust + Tauri v2 + Svelte + Plotly.js 實作的移植版，功能與 Python 版本保持對等。

### 環境需求

- [Node.js](https://nodejs.org/) 18 以上
- [Rust](https://rustup.rs/) stable (1.80+)
- Tauri CLI：`cargo install tauri-cli --version "^2"`

### 安裝與開發啟動

```bash
cd desktop-tauri
npm install
npm run tauri dev
```

### 生產建置

```bash
cd desktop-tauri
npm run tauri build
```

建置產出的安裝包位於 `desktop-tauri/src-tauri/target/release/bundle/`。

### 功能對應

| 功能 | Python 版 | Tauri 版 |
|---|---|---|
| 三層資料夾選擇 | ✓ | ✓ |
| 顯示模式（Norm / Raw / Base） | ✓ | ✓ |
| Drop 對齊時間軸（t=0 為 drop） | ✓ | ✓ |
| 施藥視窗 drop 偵測 | ✓ | ✓ |
| Baseline 準確度警示 | ✓ | ✓ |
| 可設定 timing 參數 | ✓ | ✓ |
| Medicine metadata 記錄 | ✓ | ✓ |
| 手動 sample 排除 | ✓ | ✓ |
| Dixon Q10 outlier review | ✓ | ✓ |
| 描述統計 + One-way ANOVA | ✓ | ✓ |
| Brown-Forsythe variance check | ✓ | ✓ |
| Shapiro-Wilk normality test | ✓（需 SciPy） | — (not available) |
| Robust outlier review (MAD) | ✓ | ✓ |
| ANOVA Dixon sensitivity preview | ✓ | ✓ |
| Overlay 圖例色塊 | ✓ | ✓ |
| 統計結果 CSV 匯出 | ✓ | ✓ |
| PNG 圖表匯出 | ✓ | ✓ |

### 操作流程（Tauri 版）

1. 啟動 App 後，在 **Root path** 貼上或瀏覽實驗根目錄。
2. 點選 **Refresh List**，依序從 **Step 1 / 2 / 3** 選取資料夾。
3. 選完 Step 3 後，左側會出現 **Sample Exclusion** 清單，顯示所有 `.xlsx` 的 `[IN]` / `[OUT]` 狀態。
4. 展開 **Medicine Metadata** 可填入藥品資訊；所有變更自動儲存至資料夾內的 `.skin_analysis_metadata.json`。
5. 展開 **Timing Parameters** 可調整 baseline 長度、施藥時間、搜尋容差與 baseline 警示門檻（只影響本次工作階段）。
6. 選擇 **Display Unit**（Normalized / Raw / Baseline Only）。
7. 在 **Visual Options** 開啟 **Overlay Mode** 可疊加多組實驗；**Group Color** 同組使用同色。
8. 點選 **Load & Plot** 載入並繪圖；時間軸以偵測到的 drop 為 `t = 0`。
9. 點選 **Statistics** 對目前 Step 1 + Step 2 底下的所有 Step 3 子資料夾執行統計分析，包含描述統計、ANOVA、Dixon Q review 與 robust outlier review。
10. 在統計結果面板點選 **Export CSV** 匯出完整統計報表。
11. 點選 **Export Plot** 儲存目前圖表為 PNG。

### Rust 後端測試

```bash
cd desktop-tauri/src-tauri
cargo test
```

---

## 測試與驗證

```bash
cd "Python version"
python3 -m unittest discover
python3 -m py_compile main.py skin_analysis/*.py
```

`Python version/tk_macos_smoke_test.py` 是手動 GUI smoke test，可用來檢查 macOS 的 Tk 元件是否正常互動。

## 常見問題

### 找不到檔案或資料夾

- 請先確認 `Root Path` 是否正確，並按過 `Enter` 或 `Refresh List`
- 請確認 `ROOT` 底下確實有實驗資料夾
- 請確認目標資料夾中真的有 `.xlsx` 檔案

### Excel 檔案讀不到

- 請確認檔案格式是 `.xlsx`
- 請確認欄位名稱包含 `pF - Plot 0`

### GUI 控制元件無法互動

- 先執行 `cd "Python version" && python3 tk_macos_smoke_test.py`
- 若 smoke test 也有問題，通常是本機 Python/Tk 環境，不是主程式邏輯
- 詳細處理方式請看 [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md)

Tauri folder layout note: the desktop-tauri edition now matches the Python edition. The selected root path is scanned for direct child experiment folders, and each experiment folder contains its `.xlsx` sample files plus optional `.skin_analysis_metadata.json`.
