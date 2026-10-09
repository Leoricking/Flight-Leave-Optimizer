# ✈️ Flight Leave Optimizer v0.6.3

**繁體中文 / English | Windows 10/11 · Python 3.11+ · Streamlit · SQLite · SerpApi · Ollama**

從竹南出發，依旅行天數、台灣假日及請假額度列出可行的旅遊日期，查詢已知機票報價，評估總成本與目的地可用時間，累積本機歷史資料。支援定期監控、Excel/CSV 匯入匯出、SQLite 備份還原與本機 Ollama 輔助分析。

> **價格聲明：** 搜尋價格不是保證可購買的票價。`INDICATIVE` 可能缺少已確認的回程；`TEST` 是沙盒資料。訂票前請至航空公司或售票網站重新確認座位、行李、稅費及付款金額。
>
> **版本紀錄：** 請見 [CHANGELOG.md](CHANGELOG.md)。本 README 僅說明 **v0.6.3** 的使用方式。

## v0.6.3 主要修正：離線歷史排名

- 「排名資料模式」新增 **歷史最低價（SQLite）／最近一次歷史報價（SQLite）／本次搜尋（Session）**。預設讀取歷史最低價；不會耗用 SerpApi API 額度。
- 航班排名依目前選擇的旅行日期範圍、請假天數與附加費用重新計算；歷史結果必須重新核價。
- 完整 Excel 另外輸出「歷史日期最低票價」、「歷史航班排名」、「最近日期報價」、「最近航班排名」，含 `observed_at`；原有工作表與 SQLite 原始快照保持不變。
- **歷史最低價不是即時可購價**；本次查價結果與歷史報價分開保存與顯示。
- 過去同一組日期如有多次報價，歷史最低價選最低觀察值；最近一次報價先按觀察時間再按最低價選擇。預設不把 TEST 模式當作真實歷史排名。

## 主要功能 / Features

| 功能 | v0.6.3 狀態 / Notes |
| --- | --- |
| 旅行日期與請假最佳化 | 依週末與 `data/holidays.csv` 列出符合限制的日期；可比較請假 2／3 天 |
| 航班價格來源 | SerpApi Google Flights、Duffel、手動 CSV；API 皆需要各自的金鑰或權限 |
| 航班排序 | 票價、含預估附加成本、目的地可玩時間、每小時旅遊成本 |
| 報表 | 所有日期最低已知票價、航班排名、歷史報價快照、Excel/CSV |
| 歷史保存 | `data/price_history.sqlite3`，記錄每次取得的價格快照與原始查詢時間 |
| 歷史分析 | 價格折線、觀察快照 K 線、EMA、MACD、RSI、低點統計 |
| AI 輔助 | 本機 Ollama `llama3` 敘述分析；不會替你取得即時報價 |
| 預測情境 | 只對符合條件的同質來回報價、足夠觀察天數進行低信心 7 日情境估計 |
| 排程查價 | `automation.py` 搭配 Windows 工作排程器，每日早晚檢查 |
| 資料管理 | 匯入舊版 `.xlsx`／`.csv`，重複快照去重，SQLite 備份、驗證與還原 |
| Windows 修正 | 使用記憶體 SQLite 快照，避免暫存 `backup.sqlite3` 的 WinError 32 |

## 1. 安裝與啟動 / Install & Run

先安裝 Python 3.11+（建議 Python 3.12）。專案不要求虛擬環境。於 Windows PowerShell：

```powershell
cd "C:\Users\Rossi\Documents\Claude\Flight-Leave-Optimizer"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

也可雙擊 `START_WINDOWS.bat`，它會安裝相依套件後啟動。瀏覽器開啟 <http://localhost:8501>。標題及「版本與檔案檢查」應顯示 `v0.6.3-HISTORY-RANKING`。

若要從 ZIP 更新既有專案，**先停止 Streamlit 與背景查價**，將新 ZIP 解壓到與原專案**不同**的資料夾，再於新版資料夾執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\UPDATE_EXISTING_WINDOWS.ps1 -Target "C:\Users\Rossi\Documents\Claude\Flight-Leave-Optimizer"
```

更新腳本不會覆蓋 `data/`、`.env`、`.git/`；當來源與目標相同時會主動停止。更新前仍建議自行備份資料庫與密鑰。

## 2. 搜尋機票與比較請假 / Flight & Leave Search

1. 在左側輸入出發／目的地機場（例如 `TPE`、`CTS`）、最早出發／最晚回程、旅行日數（含飛行日）。
2. 選擇最多請 2 天、3 天，或「同時比較 2 天與 3 天」。程式依 `data/holidays.csv` 與一般週末產生合法組合；公司特殊補班或假別請自行檢查日曆。
3. 選擇票價來源：
   - **SerpApi Google Flights**：輸入 SerpApi API Key；「查詢完整去回程時刻」會增加 API 使用量。
   - **Duffel API**：輸入 Duffel Token；測試帳號只能得到沙盒報價。
   - **手動匯入 CSV**：適用自行從 Trip.com、Skyscanner 等核對的價格。
4. 設定查詢日期組數，按「一鍵搜尋所有選取日期的票價」。結果包含**未取得票價**的合法日期，絕不補造價格。
5. 依最低票價、總成本、每小時成本或可玩時間排序，下載 Excel/CSV 報表。

地面交通、機場過夜與行李費為**使用者輸入的預算**，並非即時台鐵／機捷報價；也未自動驗證竹南出發是否趕得上特定航班。

**票價資料類別 / Quote modes**：

| 標記 | 意義 |
| --- | --- |
| `INDICATIVE` | 參考來回價；不一定有已確認回程班次 |
| `SEARCH_RESULT` | 已配對去回程的搜尋結果，仍需訂票前核價 |
| `MANUAL` | 使用者匯入或自行確認的價格 |
| `TEST` | API 沙盒測試價，不代表實際售價 |
| `LEGACY_UNDATED` | 舊報表缺少原始查價時間，不納入歷史技術指標／預測 |

## 3. Excel／CSV 匯入、備份與還原 / Import, Backup & Restore

在頁面 **「v0.6｜歷史資料匯入、備份與還原」** 使用：

- **匯入**：選擇 v0.3–v0.6 的 `.xlsx` 或 `.csv`，先預覽，再按「確認匯入、合併並去重」。若檔案沒有 `observed_at`／`checked_at`，會標為 `LEGACY_UNDATED`；不以匯入日冒充當年的報價時間。
- **匯出**：「完整 Excel」包含合法日期、排名、歷史快照及說明；「完整歷史 Excel」專用於分析與回匯。
- **SQLite 備份**：點「建立 SQLite 完整備份」，完成後再點「下載 SQLite 完整備份」。新版不使用 Windows 暫存 SQLite 檔案。
- **SQLite 還原**：先停止背景查價、下載目前資料庫備份，再上傳備份檔，通過格式與完整性驗證並人工確認後還原。**還原會取代整份現有歷史庫**，不是合併。

本機歷史資料保存在 `data/price_history.sqlite3`。更新、清理、搬移專案時務必保留；`backup/` 應只在本機或安全備份位置保存，不上傳公開儲存庫。

## 4. 歷史圖表、MACD／RSI 與 Ollama / Analytics & AI

「歷史機票價格研究」提供報價折線圖、觀察快照 K 線、EMA12／26、MACD(12,26,9)、RSI14、價格低點及歷史表格。選擇**同一出發日、回程日、資料來源、價格類型**後比較，避免混合不同航班的價格。

> 機票不是股票：K 線僅按**實際查詢快照**聚合。一天只有一個價時 O/H/L/C 會相同；資料不足時 MACD／RSI 與預測可能為空。沒有可直接免費回溯所有舊機票成交價的資料來源。

本機使用 Ollama：

```powershell
ollama pull llama3
ollama list
```

確認 Ollama 服務可連到 `http://127.0.0.1:11434`，在分析區填入 `llama3`，按「用 Ollama 分析歷史票價」。模型只依程式提交的歷史數據產生解說；**不會憑空產生即時票價或保證最低買點**。

## 5. Windows 每日自動查價 / Scheduled Monitoring

先在 UI **「v0.5｜無人值守排程與買票時機研究」** 設定搜尋日期、請假範圍、每次查詢組數、每日 API 限額、提醒門檻，按「儲存排程設定」。在本機設定 SerpApi Key：

```powershell
# 建議在 data\serpapi_key.txt 以單行存放金鑰，或使用 SERPAPI_API_KEY 使用者環境變數
python automation.py --dry-run   # 只產生日期，不消耗 API
python automation.py             # 正式執行一次，會消耗 API 額度
powershell -ExecutionPolicy Bypass -File .\INSTALL_SCHEDULE.ps1
```

預設每日 **08:00、20:00** 執行，執行程式為 `automation.py`，不需要 Streamlit 開著；但 Windows 電腦必須開機連網，且預設排程依使用者登入狀態執行。可透過 `REMOVE_SCHEDULE.ps1` 移除排程。

- 排程設定：`data/monitor_config.json`
- 使用量與輪巡狀態：`data/monitor_state.json`
- 查價紀錄：`data/monitor_log.jsonl`、`data/scheduled_output.log`
- 命中門檻文字提醒：`data/latest_alerts.txt`（**尚無手機／Email 推播**）

預設 `confirm_return=false` 以省 API 額度，此時很多記錄是 `INDICATIVE`，**不適合用來做嚴格的完整航班時間或可購票價預測**。啟用完整回程確認將增加呼叫次數。SerpApi 的免費額度、費率與 API 條款以官方當前公告為準。

## 6. 測試、疑難排解與安全 / Testing & Troubleshooting

```powershell
python -m pip install pytest
python -m pytest -q
python -m compileall -q .
powershell -ExecutionPolicy Bypass -File .\VERIFY_VERSION_WINDOWS.ps1
```

**`WinError 32`／看不到歷史圖表**：先確認畫面是 v0.6.3，`history_io.py` 應使用 `snapshot.serialize()`，不應再包含 `TemporaryDirectory`；再重新啟動 Streamlit。舊版備份發生例外會中斷畫面後面的 K 線、MACD、RSI 區塊。

**歷史圖沒有指標或預測**：確認資料庫確實有**多個不同查價日期**的同質報價，且不是 `TEST`／`LEGACY_UNDATED`；不是每筆候選旅行日期都能當成時間序列。

**查不到價或 API 錯誤**：先檢查金鑰、API 額度、回程確認設定、服務商覆蓋情況；未知報價保持「未取得」。

**Git 安全**：不要提交 API Key、`.env`、SQLite 資料庫、備份、含個人內容的 CSV、監控紀錄等；更新 `.gitignore` 不會取消 Git 已追蹤檔案。

---

## English quick start

Flight Leave Optimizer v0.6.3 generates leave-compatible travel date pairs, queries flight prices with SerpApi or Duffel (credentials required), imports manually verified CSV quotes, ranks routes by cost and usable time, and stores local price snapshots in SQLite. It includes historical charts, local Ollama commentary, Excel/CSV exports and imports, SQLite backup/restore, and optional twice-daily Windows Task Scheduler monitoring.

1. Install Python 3.11+, run `python -m pip install -r requirements.txt`, then `python -m streamlit run app.py` (or double-click `START_WINDOWS.bat`).
2. Open `http://localhost:8501`, set airports, date window, trip length and leave-day budget. Enter your API key, or import CSV. **Never treat test or indicative prices as confirmed bookable fares.**
3. Use **History Import, Backup & Restore** to preview Excel/CSV imports, preserve original `observed_at`, export your full history, create a SQLite backup or restore one after confirmation.
4. To collect historical quotes, configure the monitor and run `python automation.py --dry-run`, then `python automation.py`. Install the Windows 08:00/20:00 schedule with `INSTALL_SCHEDULE.ps1` if desired.
5. Historical candles, MACD, RSI, Ollama commentary and exploratory forecasts depend on comparable observations collected on **different dates**; they do not predict guaranteed flight-price minima.
6. Preserve `data/price_history.sqlite3`, local API secrets and monitor configuration when upgrading. For release history, see [CHANGELOG.md](CHANGELOG.md).

**Not yet supported:** live ground-transport timetables, guaranteed future lowest-price prediction, universal historical airfare retrieval, mobile/email notifications, and unrestricted scraping of booking websites.
