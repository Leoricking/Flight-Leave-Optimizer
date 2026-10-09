## [0.6.3] - 2026-10-09

### Fixed
- Streamlit 重啟後 Session 報價為空，導致航班排名 Excel 只有標題；新版可直接從 SQLite 取得歷史資料，無須重新查 API。
- 獨立保留本次搜尋／歷史最低價／最近一次歷史報價三種顯示模式，避免過期報價當成即時售價。

### Added
- `history_ranking.py`：依合法旅行日期回填已觀察報價、計算各種排名，保留 `observed_at`。
- Excel 新增四個歷史摘要與排名工作表；原有本次排行及完整歷史快照仍保留。

# Changelog / 版本變更紀錄

本文件依專案現有各版 README、原始碼與已交付版本整理；不代表每項功能皆已在使用者 Windows 環境完成端對端驗證。歷史變更按版本倒序排列。

格式參考 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)；版本使用既有專案編號。

## [0.6.2] — 2026-10-09
### Fixed / 修正
- 增加 `v0.6.2-WINBACKUP-FIX` 版本識別與實際載入檔案路徑顯示，用來診斷新舊檔案未正確覆蓋的情況。
- 提供 `UPDATE_EXISTING_WINDOWS.ps1` 與 `VERIFY_VERSION_WINDOWS.ps1`，協助 Windows 使用者在**不同來源／目標目錄**安全更新與驗證。
- 更新腳本備份舊程式檔，不覆蓋 `data/`、`.env` 或 `.git/`。
### Documentation / 文件
- README 統一以 v0.6.2 為主；歷史改動移至本 CHANGELOG（本次文件整理）。

## [0.6.1] — 2026-10-09
### Fixed / 修正
- SQLite 完整備份改為記憶體快照 `sqlite3.Connection.backup()` + `serialize()`，避免 Windows 暫存 `backup.sqlite3` 因檔案鎖定引發 `PermissionError [WinError 32]`。
- 備份改為由使用者按鈕觸發，避免 Streamlit 每次重新執行頁面就生成備份。
- SQLite 備份驗證與還原使用記憶體資料庫，還原前保留可回復的備份。
- 確認歷史價格 K 線、MACD、RSI、Ollama 功能未被移除；先前因備份錯誤中斷後續畫面渲染。

## [0.6.0] — 2026-10-09
### Added / 新增
- 匯入舊版 Excel `.xlsx` 與 CSV，包括航班排名、日期摘要、歷史報價快照。
- 保存原始 `observed_at`／`checked_at`，自動辨識及跳過重複報價。
- 將無原始查價時間的舊資料標為 `LEGACY_UNDATED`，排除技術指標與預測，以免偽造歷史時間序列。
- SQLite 完整備份、檔案驗證、確認後還原；歷史 Excel 增加時間欄位及資料說明。
- 匯入後重新讀取歷史數據供圖表與 Ollama 分析。

## [0.5.0] — 2026-10-09
### Added / 新增
- `automation.py` 無人值守監控程式，不依賴 Streamlit GUI。
- Windows 工作排程器腳本，預設 08:00 與 20:00 查價。
- `data/monitor_config.json` 設定、每日 API 使用限制、日期輪巡、執行紀錄及本地低價文字提醒。
- `forecast.py`：相同旅行日期、來源與價格類型的歷史樣本符合觀察量要求後，提供未來 7 日低信心價格情境。
### Known limitations / 限制
- 預設為節省 API 額度的參考報價模式，可能缺少已確認回程；無手機或 Email 推播；預測未經正式回測校準。

## [0.4.0] — 2026-10-09
### Added / 新增
- SQLite 歷史機票報價快照、觀察價格折線與 K 線。
- EMA12／EMA26、MACD(12,26,9)、RSI14 與價格低點統計。
- 本機 Ollama `llama3` 對已保存資料進行繁體中文說明。
### Notes / 說明
- 機票 K 線為觀察報價聚合，非金融市場成交 OHLC；資料不足時技術指標沒有可靠解釋力。

## [0.3.0] — 2026-10-09
### Fixed / 修正
- Excel 匯出從 `artifact_tool` 改為一般 Windows Python 可安裝的 `pandas` + `XlsxWriter`。
### Added / 新增
- 所有可行日期與其最低已知票價、航班排名、來源與報價狀態。
- CSV UTF-8 輸出及無報價日期保留機制。

## [0.2.0] — 2026-10-09
### Added / 新增
- SerpApi Google Flights 查價來源，可先查參考來回價，再依選項精查去回程航班。
- 支援請假 2 天／3 天行程對照及多日期批次搜尋。
- 顯示資料模式，區分 `INDICATIVE`、`SEARCH_RESULT`、`TEST`、`MANUAL`。

## [0.1.0] — 2026-10-09
### Initial release / 初版
- 依出回程區間、旅行日數、台灣週末／指定假日與請假上限產生旅行日期。
- Duffel API 查詢（需要 Token）與手動 CSV 報價匯入。
- 竹南至桃機預估交通、行李與必要過夜成本，計算總成本與目的地可用時間。
- Streamlit 網頁介面、Windows 啟動批次檔與初始報表輸出。

---

## Roadmap / 尚未完成

- 訂票網站完整價格覆蓋、跨供應商即時驗價與實際可購買價保證。
- 竹南→桃機大眾運輸即時班次與趕機可行性校驗。
- 經過多航線歷史回測與量化驗證的最低價預測模型。
- 手機推播、Email 告警與雲端全天候工作節點。
