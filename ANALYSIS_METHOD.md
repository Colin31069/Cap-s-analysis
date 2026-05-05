# 皮膚電容分析流程說明

這份文件說明此工具如何分析實驗資料。內容聚焦在資料如何被讀取、處理、判讀與繪圖，不說明程式語言或程式碼寫法。

## 分析目標

此工具用來比較不同實驗檔案中的電容變化。每一個 `.xlsx` 檔案代表一條量測訊號，程式會先建立該檔案自己的 baseline，再找出疑似施藥後的反應起點，也就是 drop time，最後把所有曲線對齊到同一個反應時間點，方便比較不同 sample 的變化。

主要分析結果包含：

- 初始 baseline 平均電容
- drop time，也就是反應起點
- 末端平均電容與 baseline 的差值
- normalized 百分比變化
- baseline 是否可能不穩定
- drop time 是否來自指定施藥時間窗，或是 fallback 自動搜尋

## 輸入資料格式

程式把選定根目錄下的每個直接子資料夾視為一組實驗。每組實驗資料夾內可以放多個 `.xlsx` 檔案，每個檔案會獨立分析。

資料範例：

```text
ROOT/
  Experiment A/
    1.xlsx
    2.xlsx
    .skin_analysis_metadata.json
  Experiment B/
    1.xlsx
    2.xlsx
```

每個 Excel 檔案必須包含欄位 `pF - Plot 0`。這一欄會被視為原始電容訊號，單位是 pF。

如果檔案無法讀取、沒有這個欄位，或資料是空的，該檔案會被略過，不會進入繪圖。

每組實驗資料夾也可以在 `.skin_analysis_metadata.json` 中保存人工踢除清單。清單只記錄 `.xlsx` 檔名與原因，不會刪除或改名原始檔案。

## 時間軸假設

程式目前假設資料點的取樣間隔是 `0.1` 秒。也就是說：

- 第 1 筆資料時間為 0 秒
- 第 2 筆資料時間為 0.1 秒
- 第 101 筆資料時間約為 10 秒

所有秒數設定，例如 baseline duration、drug apply time、apply window，都會用這個 0.1 秒間隔轉成資料點數。

## Baseline 的建立

每個檔案會先用訊號開頭的一段資料建立自己的 baseline。預設 baseline duration 是 20 秒。

baseline 的用途有三個：

1. 作為該 sample 的初始電容基準。
2. 作為 normalized 顯示模式中的 100% 參考值。
3. 作為 drop 偵測門檻的計算基礎。

baseline 平均值是 baseline 視窗內所有電容值的平均。這個值在圖例中顯示為 `Base`。

如果使用者設定的 baseline duration 太長，導致 baseline 視窗與施藥搜尋區間重疊，程式會自動縮短 baseline，讓 baseline 停在施藥搜尋區間之前。這樣可以避免把施藥反應混入初始基準。

## 施藥時間窗與 Drop 偵測

工具有兩個重要時間設定：

- `Drug Apply Time (s)`：使用者預期施藥大約發生的時間，預設 25 秒。
- `Apply Window +/- (s)`：允許搜尋 drop 的前後時間範圍，預設正負 5 秒。

例如預設設定下，程式會優先在 20 秒到 30 秒之間找反應起點。

drop 偵測的門檻由 baseline 計算：

```text
drop threshold = baseline 平均值 + 3 * baseline 標準差
```

如果 baseline 的標準差非常小，程式會使用一個極小的最低值，避免門檻變得不合理。

程式會從 baseline 結束後，以及施藥搜尋區間開始後，兩者較晚的時間點開始搜尋。第一個高於門檻的資料點會被視為 drop time。

## Fallback 自動搜尋

如果程式在使用者指定的施藥時間窗內找不到超過門檻的資料點，就會啟用 fallback 自動搜尋。

fallback 會從 baseline 結束後開始，往後最多搜尋 500 個資料點。因為每點間隔 0.1 秒，所以最多約 50 秒。

如果 fallback 也找不到超過門檻的點，drop time 會退回 baseline 結束時間。

當使用 fallback 時，工具會顯示 timing warning，提醒這條曲線的 drop time 不是在指定施藥時間窗內找到的。這不代表資料一定錯誤，但代表使用者應該人工確認施藥時間或訊號形狀。

## Delta 的計算

每條曲線的 delta 使用末端平均電容減去 baseline 平均電容：

```text
delta = 最後 100 個資料點的平均電容 - baseline 平均電容
```

如果資料少於 100 點，程式目前不計算有效的末端平均，因此 delta 會是無效值。

在 raw 顯示模式中，delta 以 pF 顯示。在 normalized 顯示模式中，delta 會轉成相對 baseline 的百分比變化。

## 圖表時間對齊方式

每條曲線偵測到 drop time 後，繪圖時會把 drop time 對齊到 0 秒。

也就是說，圖上的時間軸不是原始量測時間，而是相對於反應起點的時間：

```text
圖上時間 = 原始時間 - drop time
```

這樣做的目的是讓不同 sample 的反應起點重疊，方便比較反應前後的形狀與幅度。

如果開啟 `Show Drop Lines`，圖上的垂直線會出現在 0 秒位置，代表各曲線對齊後的 drop 參考點。

## 顯示模式

### Normalized (%)

這是預設顯示模式。每條曲線會用自己的 baseline 平均值當作 100%。

```text
normalized value = 原始電容 / baseline 平均電容 * 100
```

這個模式適合比較不同 sample 的相對變化，尤其當不同檔案的初始電容值不完全相同時。

### Raw Data (pF)

這個模式顯示原始電容值，單位是 pF。時間軸仍然會以 drop time 對齊到 0 秒。

這個模式適合檢查實際電容大小、雜訊程度、漂移情況，以及偵測到的 drop 是否合理。

### Baseline Only (Raw Baseline Window)

這個模式只顯示 baseline 視窗內的原始資料。它主要用來檢查 baseline 是否穩定。

雖然只顯示 baseline 區段，時間軸仍然使用 drop time 對齊後的相對時間。

## Baseline 穩定度警示

程式會檢查 baseline 是否可能不穩定。預設警示門檻是 2%。

目前有兩種 baseline 警示判斷：

1. 尾端均值偏移：取 baseline 最後 20 個資料點的平均，和整段 baseline 平均比較。如果偏移幅度達到門檻，就標記警示。
2. 連續上升：對 baseline 做 5 點 rolling mean，如果出現至少 10 次連續上升，且上升後的偏移達到門檻，就標記警示。

警示狀態分為：

- `ok`：沒有觸發警示。
- `warning`：觸發其中一種 baseline 警示。
- `inaccurate`：兩種 baseline 警示都觸發。

這些警示只提醒使用者注意資料品質，不會自動排除檔案，也不會改變 normalized 的 baseline 定義。

在圖例中，可疑資料會加上 `[注意]` 或 `[不準確]`。程式也會跳出警示視窗列出受影響的 sample 與原因。

## 手動踢除 sample

工具支援由使用者人工選定要排除的 `.xlsx` sample。這個功能只會讓該檔案不進入繪圖與統計分析，不會修改原始 Excel 檔。

排除上限依目前實驗資料夾中的 `.xlsx` 數量決定：

```text
n < 5: 0
n >= 5: floor(n / 5)
```

例如 `n=5` 到 `n=9` 最多可排除 1 筆，`n=10` 到 `n=14` 最多可排除 2 筆。這個上限是人工品質判斷的保護欄，不代表程式自動判定 outlier。

採用這個設計的原因是，多數正式報告規範會要求事先定義排除標準，並回報每組實際排除的資料與最後分析的 `n`。ARRIVE guideline 要求說明 inclusion/exclusion criteria、逐組回報未納入分析的資料點及原因，並回報每組確切 `n`；GraphPad Prism 說明 outlier identification 沒有單一通用標準，Grubbs 偏向單一 outlier，ROUT 才支援多筆；NIST generalized ESD 也要求先指定最多可能 outlier 數量。參考來源：

- ARRIVE 3a: https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3a/explanation
- ARRIVE 3b: https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3b/explanation
- ARRIVE 3c: https://arriveguidelines.org/arrive-guidelines/inclusion-and-exclusion-criteria/3c/explanation
- GraphPad outlier guide: https://www.graphpad.com/guides/prism/8/statistics/stat_how_to_removing_outliers.htm
- GraphPad ROUT method: https://www.graphpad.com/guides/prism/latest/statistics/stat_how_it_works_rout_method.htm
- NIST generalized ESD: https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h3.htm

## 圖例與標題

每條曲線的 sample 名稱來自 Excel 檔名，不包含副檔名。例如 `1.xlsx` 會顯示為 `N 1`。

如果使用詳細圖例，圖例可以顯示：

- baseline 平均值
- delta
- baseline 品質標記

圖表標題會使用實驗資料夾名稱，並附上使用者輸入的藥品名稱與劑量。藥品資訊來自該實驗資料夾中的 `.skin_analysis_metadata.json`。

## 疊圖與顏色

工具可以把多次載入的實驗疊在同一張圖上。開啟 overlay mode 時，新的曲線會保留既有圖上的曲線，方便跨實驗比較。

如果開啟 experiment color，同一次載入的實驗會使用同一組顏色，不同 sample 用不同線型區分。這有助於從圖上分辨不同實驗來源。

## 統計分析方法

統計分析使用 `Delta %` 作為主要 endpoint。每一個 `.xlsx` 檔案代表一片獨立電極片，因為不同電極片的初始電容可能不同，所以會先用該電極片自己的 baseline 做標準化：

```text
Delta % = delta pF / baseline pF * 100
```

統計視窗會掃描目前 root path 底下的所有直接子資料夾。每個子資料夾會被視為一個濃度組，資料夾名稱就是濃度標籤。

手動踢除的 sample 不會進入 `Delta %`、描述統計或 one-way ANOVA。統計視窗與 CSV 會列出被排除的檔名與原因；描述統計中的 `n` 是排除後實際納入分析的 sample 數。

工具也支援 Dixon's Q `Q10` test 作為明確的單一異常值建議。Dixon Q 只在每組納入分析後 `n=3` 到 `n=10` 時執行，並且只檢查排序後的最低值與最高值：

```text
Q = gap / range
```

其中 `gap` 是可疑端點和最近鄰資料點的距離，`range` 是該組最大值與最小值的距離。這版使用 `α=0.05` 的內建 critical value table，數值參考 [LibreTexts Dixon's Q-Test critical values](https://chem.libretexts.org/Ancillary_Materials/Reference/Reference_Tables/Analytic_References/Appendix_06%3A_Critical_Values_for_Dixons_Q-Test)。如果 `Q > Qcritical`，程式會列出 `Recommended Dixon Exclusions`，並在 Statistics 報告中提供「排除 Dixon 建議樣本後」的 ANOVA sensitivity preview。這個 preview 不會自動改 metadata；使用者仍需在 `Sample Exclusion` 中確認並保存原因。

一般人工排除規則仍是 `n < 5` 不排除、`n >= 5` 最多 `floor(n / 5)`。唯一例外是 `n=3` 或 `n=4` 且 Dixon Q 通過 `α=0.05` 時，工具允許保存一筆 `method=dixon_q` 的排除紀錄。

統計視窗也會做 `Outlier Review`，但這不是自動踢除規則。程式只在每組納入分析後 `n >= 5` 時，對每一筆 `Delta %` 用同組其他 sample 計算 leave-one-out median 與 MAD，再計算：

```text
modified z = 0.6745 * (Delta % - peer median) / peer MAD
```

如果 `abs(modified z) >= 3.5`，該 sample 會被列為候選 outlier，提醒使用者回頭檢查原始曲線、baseline/timing warning 與實驗紀錄。候選樣本不會自動排除，也不會寫入 metadata；只有使用者在 `Sample Exclusion` 手動排除時，才會保存排除原因。

每個濃度組會列出描述統計：

- sample 數量 `n`
- mean、SD、SEM
- median、IQR
- 95% confidence interval

組間比較使用 one-way ANOVA。這個檢定用來判斷所有濃度組的平均 `Delta %` 是否存在整體差異，也就是是否至少有一個濃度組的平均值和其他組不同。

one-way ANOVA 會列出：

- F 值
- between-groups 與 within-groups 自由度
- p-value
- eta-squared
- omega-squared

這版統計分析只包含 one-way ANOVA，不包含兩兩比較或事後比較。如果 ANOVA 顯著，只能說明濃度組之間存在整體差異；若需要判斷哪兩組不同，應依課程或實驗規範另行決定是否做事後比較。

統計視窗也會顯示假設檢查：

- Shapiro-Wilk normality check：每組 `n >= 3` 時執行。
- Brown-Forsythe variance check：至少兩組各有 `n >= 2` 時執行。

如果 `scipy` 未安裝，描述統計與 ANOVA 的 F 值仍可顯示，但 p-value、95% confidence interval 與假設檢查會標示為不可用。若樣本數太少，例如某組 `n < 2` 或 `n < 3`，工具會顯示警示並略過不適合的推論統計。

## 結果判讀建議

分析結果應搭配原始曲線形狀一起判讀，不建議只看單一數值。

建議優先確認：

1. baseline 區段是否平穩。
2. drop time 是否落在預期施藥時間附近。
3. 是否出現 fallback timing warning。
4. normalized 曲線是否因 baseline 太小或不穩而被放大。
5. delta 是否代表實驗真正想比較的末端狀態。

如果資料出現 `[注意]` 或 `[不準確]`，建議切換到 raw 或 baseline only 模式檢查該 sample，再決定是否納入解讀。

## 目前分析限制

目前程式採用固定取樣間隔 0.1 秒。如果 Excel 實際取樣間隔不同，時間軸與秒數設定會不準。

drop 偵測使用的是「超過 baseline 平均值加 3 倍標準差的第一個點」。如果訊號反應方向不是上升、雜訊很大、或施藥前已有漂移，drop time 可能不準。

delta 使用最後 100 個資料點的平均，因此它描述的是量測末端狀態，不一定代表最大反應、反應速度或曲線下面積。

baseline 警示是品質提示，不是統計檢定。它能幫助找出明顯漂移或上升的 baseline，但不能保證沒有警示的資料一定完全可靠。

## 建議人工檢查流程

1. 先用 `Normalized (%)` 查看整體相對變化。
2. 查看圖例是否有 `[注意]` 或 `[不準確]`。
3. 如果有警示，切到 `Baseline Only (Raw Baseline Window)` 檢查 baseline。
4. 切到 `Raw Data (pF)` 確認實際電容值與 drop 位置。
5. 檢查 timing warning，確認 drop 是否真的落在施藥時間窗內。
6. 最後再根據實驗設計判斷是否採用該 sample 的 delta 或 normalized 變化。
