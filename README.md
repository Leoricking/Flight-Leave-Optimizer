# Flight Leave Optimizer v0.6 — History Import / Restore (繁體中文 / English)

## 新增功能 / What's new

- Excel `.xlsx`：支援舊版「航班排名」、「所有日期最低票價」及新版「歷史報價快照」；優先匯入時間資訊最完整的工作表，避免重複。
- CSV：自動識別排名、日期摘要及完整歷史快照；只有日期摘要但缺少票價的列會忽略。
- `observed_at`：保存原始查價時間，正規化為 UTC；舊檔的 `checked_at` 亦可使用。
- `LEGACY_UNDATED`：沒有查價時間的舊資料只供查閱，不使用匯入當日偽造歷史 K 線、MACD、RSI 或價格預測。
- 去重：同時間、航線、旅程、價格、航空公司、來源、模式、直飛和航班時間的相同快照自動跳過；缺乏歷史時間的相同舊資料也會被跳過。
- SQLite：線上一致性備份，還原前進行 integrity_check / 資料表和欄位驗證；還原會覆蓋整個本地歷史庫，需人工確認並停止背景排程。
- 匯入成功後 Streamlit 重新執行，更新歷史研究圖表與本機 Ollama 分析；Ollama 模型仍使用 `llama3`。
- 完整 Excel（四工作表）與獨立歷史 Excel 都新增包含 `observed_at` 的歷史資料。

## Windows 使用方式 / Usage

1. 備份原專案中的 `data\price_history.sqlite3`，或在舊版取得備份。
2. 解壓縮 v0.6 覆蓋舊程式，但**不要覆蓋 `data/` 舊資料檔**，尤其 `price_history.sqlite3`、`monitor_config.json`、`serpapi_key.txt`。
3. 在專案根目錄執行 `python -m pip install -r requirements.txt`，再雙擊 `START_WINDOWS.bat`。
4. 展開「v0.6｜歷史資料匯入、備份與還原」：上傳 `.xlsx` / `.csv`，先看預覽，點「確認匯入、合併並去重」。
5. 完整備份請下載 `SQLite 完整備份`；若要還原，先關閉工作排程、備份原庫，確認備份筆數再點還原。
6. 匯入後切換「歷史機票價格研究」，重新選擇相同出回程、來源、模式，查看走勢與 Ollama 分析。

**Note:** Non-time-stamped legacy rows cannot reconstruct historical prices. `LEGACY_UNDATED` rows are excluded from longitudinal indicators and forecasting. Import confirmation is required; restoration replaces the existing DB.

## 啟動 / Start

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 測試 / Tests

```powershell
python -m pip install pytest
python -m pytest -q
```

# Flight Leave Optimizer v0.5

**繁體中文｜Windows 10/11，Python 3.11–3.13，不需 .venv**

## 功能

- 保留 v0.4 Streamlit：請假日曆最佳化、SerpApi／Duffel、歷史 SQLite、Excel/CSV、觀察 K 線、MACD/RSI、本地 Ollama。
- **新增 `automation.py`**：獨立 CLI，自動列出旅行日期、排程查價、持續寫入 `data/price_history.sqlite3`、每日限額、輪流掃描所有日期、失敗記錄。
- **新增 Windows 工作排程器**：`INSTALL_SCHEDULE.ps1` 建立每日 08:00/20:00 排程（可自訂）。`REMOVE_SCHEDULE.ps1` 移除。
- **新增 `forecast.py`**：對固定出回程、相同來源、已選定來回的票價快照，至少 7 個不同觀察日且橫跨 7 天時顯示 7 日低信心價格情境範圍。
- **新增 GUI**：修改背景監控參數、查看查價紀錄、顯示價格情境、透過 `llama3` 說明（可選）。

## 快速開始

1. 解壓縮完整 ZIP 到 `D:\\code\\Claude\\Flight-Leave-Optimizer`；保留舊版的 `data/price_history.sqlite3`、`.env`（如有）。
2. 雙擊 `START_WINDOWS.bat`；或：

   ```powershell
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```
3. 瀏覽 `http://localhost:8501`，滑到下方 **v0.5｜無人值守排程與買票時機研究** 修改目的地、日期範圍、最多請假天數、每日配額，按「儲存排程設定」。
4. 在 SerpApi 控制台領取 API Key。Windows 永久使用者環境變數可設 `SERPAPI_API_KEY`，**或者**建立 `data/serpapi_key.txt`，內容只有 Key 單行；此檔已加入 `.gitignore`。不要上傳 Key 到 GitHub。以目前個人使用情境，推薦先採每日 8–20 筆初次搜尋，`confirm_return=false`，避免免費配額耗盡。
5. 測試日期生成（不消耗 API）：

   ```powershell
   python automation.py --dry-run
   ```
6. 測試手動查價（真實 API 請求）：

   ```powershell
   python automation.py
   ```
7. 建立工作排程（在專案根目錄 PowerShell）：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\INSTALL_SCHEDULE.ps1
   ```

   自訂時間：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\INSTALL_SCHEDULE.ps1 -MorningHour 7 -EveningHour 19
   ```
8. 在 Windows 工作排程器找到 `FlightLeaveOptimizer_PriceMonitor`。**預設僅已登入時執行**（鎖定螢幕通常可以），要登出後仍執行，請自行於工作排程器改為「不論使用者是否登入都執行」並提供憑證。電腦需要開機且連網。程式無法在關機時執行。

## 檔案

| 檔案 | 說明 |
|---|---|
| `automation.py` | 獨立排程查價入口，支援 `--dry-run`，不開啟 GUI |
| `forecast.py` | 固定行程同質價格快照與情境估計 |
| `data/monitor_config.json` | GUI 自動建立的本地監控設定，已排除 Git |
| `data/monitor_state.json` | 每日 API 呼叫數與輪替查詢進度 |
| `data/monitor_log.jsonl` | 每次查價執行與錯誤記錄 |
| `data/latest_alerts.txt` | 最新觸發的價格文字提醒，並非 Windows 通知／Email |
| `data/price_history.sqlite3` | 本機報價快照資料庫；更新程式時**務必保留** |
| `data/scheduled_output.log` | 背景執行標準輸出／錯誤 |

## 注意事項

1. SerpApi **不是免費無限查**，免費額度及條款可能調整。每次初次搜尋通常耗用 1 次 API；`confirm_return=true` 時可能額外耗用回程請求。`daily_run_limit` 只限制程式自身啟動的日期查詢，不追蹤其他工具／帳號使用額度。
2. 預設自動監控使用 `confirm_return=false` 以節約額度，此時資料為 **INDICATIVE 參考價**，不可證實完整回程班次、直飛與可玩時數。因此**不會被用於嚴格的同質來回預測**；要建立嚴格預測曲線需開啟回程確認並持續搜集。
3. 並不存在可以合法無限制還原多年逐日航空票價的通用免費 API。此程式主要從**開始運行的今天**累積快照；供應商歷史洞察另行顯示。
4. 預測只有 >=7 個獨立觀察日且橫跨 7 天才會顯示，屬未校準的趨勢外推與寬區間；不能可靠推斷「真正未來最低價」，也不保證哪一天購票最便宜。**Ollama 僅解釋預測輸出，不生成實時航空報價**。
5. 每日最低票價是「該次查詢的最低已觀察報價」，不等於市場真實最低成交價。付款前必須核價、確認行李與取消條款。
6. 每次查詢帶有 API 呼叫成本；兩次每日監控與 GUI 手動查詢的總量需自行控制。
7. 腳本沒有第三方 Telegram／Email 發送權限，因此低價提醒以本地檔案方式提供，不聲稱已推送到手機。

## English quick reference

`START_WINDOWS.bat` launches the Streamlit UI. Set `SERPAPI_API_KEY` or locally create `data/serpapi_key.txt`; run `python automation.py --dry-run`, then `python automation.py`. Install two Windows scheduled runs with `powershell -ExecutionPolicy Bypass -File .\INSTALL_SCHEDULE.ps1`. The headless worker rotates eligible dates, respects its own daily request cap, records price snapshots in SQLite, and writes JSONL run logs. The prediction module requires a minimum of seven distinct days of comparable **confirmed** roundtrip quotes and produces low-confidence scenarios, not guaranteed price minima. Never commit API keys, DB backups, or local config files.


## v0.6.1 Windows 修正
- 修正 sqlite_backup_bytes 在 Windows TemporaryDirectory 清除時觸發 WinError 32 的問題；改以 SQLite 記憶體快照 backup + serialize，避免暫存檔。
- SQLite 還原與驗證也改用記憶體快照；保留還原前備份以供復原。
- SQLite 備份改為按下建立按鈕後才執行，避免 Streamlit 重跑時反覆備份。
- v0.5 K 線 / MACD / RSI / Ollama 區塊原本未刪除，因前述例外中止渲染；已保留。
- 升級時請保留 data/price_history.sqlite3 及 API Key。

## v0.6.2: Windows 未覆蓋舊檔時的檢查與一鍵升級

若畫面仍顯示 `app.py line 162` 中直接呼叫 `sqlite_backup_bytes(history_db)`，代表電腦仍在使用 v0.6 舊版檔案；v0.6.2 的備份使用 `sqlite3.connect(':memory:')` + `serialize()`，不會以 `TemporaryDirectory` 建立 `backup.sqlite3`。

1. 結束舊的 Streamlit（其 PowerShell 視窗按 Ctrl+C）與自動排程。
2. 把 ZIP 解壓縮到**另一個資料夾**。
3. 在新資料夾開啟 PowerShell，執行：
   `powershell -ExecutionPolicy Bypass -File .\UPDATE_EXISTING_WINDOWS.ps1`
4. 若專案不是預設位置，則加上 `-Target "C:\完整路徑\Flight-Leave-Optimizer"`。
5. 同意確認後，腳本會備份舊 Python 檔案，再覆蓋程式檔；不更動 `data/`、`.git/`、`.env`。從原專案啟動 Streamlit。
6. 應在畫面看到 `v0.6.2-WINBACKUP-FIX`，可打開「版本與檔案檢查」確認載入的真實路徑。

另提供 `VERIFY_VERSION_WINDOWS.ps1` 檢查實際專案檔案。請注意，SQLite 完整備份要在頁面按「建立 SQLite 完整備份」後才會產生，不應在每次重繪時直接執行。
