# Skin Analysis 工具說明

這個專案是一個用 `Tkinter` 與 `Matplotlib` 製作的桌面 GUI 工具，用來瀏覽實驗資料夾、讀取 `.xlsx` 原始電容資料、偵測 drop 時間，並將結果以不同模式繪圖顯示。

## 環境需求

- Python 3.11 以上
- 建議在 macOS 使用 Python 3.12 以上，以降低 Tk 介面問題
- Python 版本的程式碼放在 `Python version/`，請先 `cd` 進去再執行
- 套件需求請參考 `Python version/requirements-gui.txt`

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

如果你在 macOS 遇到下拉選單、勾選框或焦點問題，請另外閱讀 [MACOS_GUI_FIXES.md](./MACOS_GUI_FIXES.md)。

## 啟動方式

```bash
cd "Python version"
python3 main.py
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

## 使用流程

1. 啟動程式後，在左側 `Root Path` 貼上實驗根目錄，或點選 `Browse...` 選取資料夾。
2. 按下 `Enter` 或 `Refresh List` 重新載入 `Experiment Folder` 清單。
3. 從清單選擇目標 `Experiment Folder`。
4. 視需要展開 `Medicine Metadata`，設定藥品數量並填入每種藥品的名稱與劑量。
5. 視需求選擇顯示模式：
   - `Normalized (%)`：以 baseline 為 100% 顯示相對變化，時間軸會以偵測到的 drop 作為 `0`
   - `Raw Data (pF)`：顯示原始電容值，時間軸會以偵測到的 drop 作為 `0`
   - `Baseline Only (Raw 20s)`：只顯示前 20 秒的 baseline 區段，但仍使用相同的相對 drop 時間軸
6. 視需求調整圖例與視覺選項：
   - `Overlay Mode`：將不同實驗資料疊加在同一張圖上
   - `Experiment Color`：同一次載入的實驗使用同色，靠線型區分不同 sample
   - `Show Drop Lines`：顯示 `0` 秒位置的垂直輔助線，也就是各條曲線對齊後的 drop 參考點
   - `Legend Customization`：控制圖例是否顯示 baseline、delta
7. 點選 `LOAD & PLOT` 載入並繪圖。
8. 圖表標題會顯示實驗資料夾名稱與藥品標記資訊。
9. 需要輸出圖片時，點選 `Export Plot` 儲存成 `.png`。

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
