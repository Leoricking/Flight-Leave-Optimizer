# Flight Leave Optimizer v0.1 / 請假 × 機票最佳化

## 繁體中文

### 功能
- 指定機場、出發與回程區間、行程天數、最多請假天數，自動列出日期組合。
- 使用 Duffel 官方 API 查詢 **來回** 航班，紀錄航班時間、航空公司、直飛、報價與效期。
- 或匯入 CSV 人工比價資料（Trip.com/Skyscanner 等自行查詢的實際報價）。
- 把竹南至桃機來回交通費、必要過夜費及行李額外費用加入總成本。
- 以總成本排名，另顯示目的地可用小時與每小時旅行成本。
- CSV 與 Excel 匯出。Test 與 Live 報價有標記；不假造報價。

### Windows 10 / Python 3.11+ 一鍵執行
1. 解壓縮，雙擊 `START_WINDOWS.bat`（使用現有 Python，不自動建立 .venv）。
2. 網頁瀏覽器進入 Streamlit 顯示的 `http://localhost:8501`。
3. 選擇「手動匯入 CSV」或「Duffel API 即時查詢」。
4. Duffel API 請自行申請 token。可在 GUI 輸入或於 PowerShell 設定 `$env:DUFFEL_ACCESS_TOKEN="..."`。
5. 查詢成功後，按「產生 CSV + Excel 報表」。

**安全提醒**：不要把 API token 寫進程式碼或提交 Git。請確認 Duffel live 帳號權限、查詢費率、航空公司覆蓋率。Test 模式返回沙盒報價，不是真實可購票價。所列價格可能失效；付款前重新驗價。

### CSV 格式
`departure_date,return_date,price_twd,airline,direct,outbound_departure,outbound_arrival,return_departure,return_arrival,source`

- 日期 `YYYY-MM-DD`，時間盡量用 `YYYY-MM-DDTHH:MM:SS+09:00` (札幌) / `+08:00` (台灣)。
- `direct`: `true`/`false` (或 `1`/`0`)。 
- `price_twd`: 每成人完整來回票價（請自行確認稅費）。
- 沒有航班時刻可以留空，可用小時成本就不計算。

### 目前限制及下一版建議
- 只有 2026/10/26 內建國定假日；`data/holidays.csv` 可加入自訂假日，公司特休與調班自行設定。
- 台鐵、高鐵、機捷、客運尚未串即時班表，交通費為估計值；沒有宣稱精準算出竹南到桃機可否趕上特定班機。
- API 會消耗額度，預設一次只查前 5 組；可調整。搜尋結果可能沒有台日航班，與供應商涵蓋率有關。
- 不執行 Trip.com / Skyscanner 非官方爬蟲，不繞過反爬或驗證機制。
- 未實作時段篩選及實際適航的班車銜接，只根據札幌到達與離開時間估計可玩時間。
- 尚未支援動態換匯：Duffel 回傳非 TWD 時不混入排名。可於未來導入有來源的 FX API。
- `data/last_api_snapshot.json` 僅為歷史快照，不是目前即時票價。

### 測試
`python -m unittest discover -s tests -v`

## English

Flight Leave Optimizer compares date combinations under a maximum leave-day budget, searches round-trip fares via the official Duffel API (credentials required), or imports manually verified price CSV data. It adds configurable ground transportation, overnight and baggage budgets, estimates usable destination hours, and exports ranked CSV/XLSX results.

To launch on Windows, double-click `START_WINDOWS.bat`. No virtual environment is created. Set a Duffel token in the application or via `DUFFEL_ACCESS_TOKEN`. Test-mode offers are **not bookable live prices**. Confirm fare availability and conditions before purchase. Edit `data/holidays.csv` to add regional holidays.
