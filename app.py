from __future__ import annotations
import os, json, time, io
from datetime import date
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from history import PriceHistory, analyze_trends
from history_io import parse_upload, import_quotes, history_excel_bytes, sqlite_backup_bytes, validate_backup, restore_backup
from analytics import observed_series, technical_indicators, price_stats
from ollama_analysis import local_models, explain
from automation import load_config, CONFIG_PATH, candidates as monitor_candidates
from forecast import daily_lows, project_price
from core import generate, holiday_set, manual_csv, join_offers
from providers import duffel_search
from serpapi_provider import serpapi_search
from report import make_summary, add_ranks, csv_bytes, excel_bytes, COLUMNS, SUMMARY_COLUMNS
from history_ranking import select_historical_offers, rank_rows

DB_PATH=Path(__file__).parent/'data/price_history.sqlite3'
history_db=PriceHistory(DB_PATH)
st.set_page_config(page_title='Flight Leave Optimizer v0.6.3',page_icon='✈️',layout='wide')
st.title('✈️ Flight Leave Optimizer v0.6.3')
st.caption('v0.6.3-HISTORY-RANKING｜一次比較請 2 天／3 天假｜機票參考價及完整行程分開呈現｜搜尋結果付款前需重新核價')
with st.expander('🔎 版本與檔案檢查', expanded=False):
    st.code(f'版本：v0.6.3-HISTORY-RANKING\napp.py：{Path(__file__).resolve()}\nhistory_io.py：{Path(__import__("history_io").__file__).resolve()}')
with st.sidebar:
    st.header('旅遊條件')
    c1,c2=st.columns(2)
    origin=c1.text_input('出發機場','TPE').upper().strip()
    destination=c2.text_input('目的地機場','CTS').upper().strip()
    start=st.date_input('最早出發日',value=date(2026,10,20))
    end=st.date_input('最晚回程日',value=date(2026,11,16))
    days=st.number_input('旅行日數（含出入境）',min_value=2,max_value=30,value=5)
    leave_mode=st.selectbox('比較請假天數',['同時比較 2 天與 3 天','最多 2 天','最多 3 天','自行指定'])
    max_leave={'同時比較 2 天與 3 天':3,'最多 2 天':2,'最多 3 天':3}.get(leave_mode)
    if max_leave is None: max_leave=st.number_input('最多請假天數',0,15,2)
    direct_only=st.checkbox('只顯示已確認的去回程直飛',value=False,help='開啟後無回程資訊的參考價會被排除')
    st.markdown('**附加成本（每人，TWD）**')
    transport=st.number_input('竹南 ⇄ 桃機交通',0,20000,1200,100)
    overnight=st.number_input('機場過夜／住宿',0,20000,0,100)
    luggage=st.number_input('行李追加成本',0,20000,0,100)
    rank_by=st.selectbox('排名方式',['最低票價','總成本最低','每小時旅遊成本最低','可玩時間最長'])

try: candidate=generate(start,end,int(days),int(max_leave),holiday_set(str(Path(__file__).parent/'data/holidays.csv')))
except Exception as e: st.error(str(e));st.stop()
if leave_mode=='同時比較 2 天與 3 天':
    candidate=[x for x in candidate if x['leave_days'] in (2,3)]
st.metric('符合條件的日期組合',len(candidate))
st.dataframe(pd.DataFrame(candidate),hide_index=True,use_container_width=True)
if not candidate:st.warning('目前條件沒有合法日期；可提高請假天數或改成 4 天行程。')

mode=st.radio('票價來源',['SerpApi Google Flights（免費額度）','Duffel API','手動匯入 CSV'],horizontal=True)
if 'offers_v02' not in st.session_state: st.session_state['offers_v02']=[]
if mode=='手動匯入 CSV':
    st.info('手動輸入或匯入自己從網站確認的報價；未提供的日期價格顯示未取得。')
    header='departure_date,return_date,price_twd,airline,direct,outbound_departure,outbound_arrival,return_departure,return_arrival,source\n'
    st.download_button('下載 CSV 範本',header,file_name='offers_template.csv')
    up=st.file_uploader('匯入 CSV (UTF-8)',type='csv')
    if up:
        try:
            blob=up.getvalue(); signature=(up.name,len(blob),hash(blob))
            if st.session_state.get('last_import_signature')!=signature:
                imported=list(manual_csv(io.StringIO(blob.decode('utf-8-sig'))))
                st.session_state['offers_v02']=imported
                history_db.save_offers(origin,destination,imported)
                st.session_state['last_import_signature']=signature
                st.success(f'已儲存 {len(imported)} 筆手動報價到本機歷史資料庫')
        except Exception as e: st.error(str(e))
else:
    if mode.startswith('SerpApi'):
        key=st.text_input('SerpApi API Key（或使用 SERPAPI_API_KEY 環境變數）',type='password') or os.getenv('SERPAPI_API_KEY','')
        st.caption('第一階段：同時取得多日期參考來回價格。第二階段：查詢指定去程對應的回程班次，額外耗用 API 額度。')
        confirm=st.checkbox('查詢完整去回程時刻（每日期增加 API 呼叫）',value=True)
        st.info('SerpApi 首次取得的參考總價可能沒有回程時間。只有第二階段配對到兩段行程後才能確認直飛和可玩時間。')
    else:
        key=st.text_input('Duffel Access Token（或使用 DUFFEL_ACCESS_TOKEN 環境變數）',type='password') or os.getenv('DUFFEL_ACCESS_TOKEN','')
        confirm=False
        st.warning('Duffel Test Token 回傳的是沙盒價格，不可當作真實機票價格。')
    limit=st.number_input('最多查詢幾組日期（避免用盡 API 額度）',1,max(1,len(candidate)),min(15,max(1,len(candidate))))
    pause=st.slider('查詢間隔（秒）',0.5,5.0,1.0,0.5)
    if st.button('🔎 一鍵搜尋所有選取日期的票價',type='primary',disabled=not candidate):
        if not key: st.error('請輸入 API Key。免費額度也必須註冊取得金鑰。')
        else:
            found=[];failed=[];all_insights=[];prog=st.progress(0)
            for i,d in enumerate(candidate[:int(limit)]):
                try:
                    if mode.startswith('SerpApi'):
                        values=serpapi_search(origin,destination,d['departure_date'],d['return_date'],key,confirm_return=confirm,max_pairings=1,insights_sink=all_insights)
                    else:
                        values=duffel_search(origin,destination,d['departure_date'],d['return_date'],key)
                    found.extend(values)
                    if values: history_db.save_offers(origin,destination,values)
                    for insight in all_insights:
                        history_db.save_insight(origin,destination,insight['departure_date'],insight['return_date'],insight['price_insights'])
                    all_insights.clear()
                except Exception as e:failed.append(f"{d['departure_date']} ~ {d['return_date']}: {e}")
                prog.progress((i+1)/int(limit))
                if i+1<int(limit):time.sleep(pause)
            st.session_state['offers_v02']=found
            st.success(f'查詢 {min(limit,len(candidate))} 組日期，取得 {len(found)} 筆結果；錯誤 {len(failed)} 組。')
            for err in failed[:8]:st.error(err)
            if found:
                snap=Path('data/last_search_snapshot.json');snap.parent.mkdir(exist_ok=True)
                snap.write_text(json.dumps(found,ensure_ascii=False,indent=2),encoding='utf-8')

# Explicitly distinguish session-only search results from saved SQLite snapshots.
all_saved_quotes = history_db.quotes(origin, destination)
view_mode = st.radio('排名資料模式', ['歷史最低價（SQLite）', '最近一次歷史報價（SQLite）', '本次搜尋（Session）'],
                     horizontal=True, help='歷史價格不是即時可購價格；不會重新呼叫 API。')
if view_mode == '本次搜尋（Session）':
    offers = st.session_state['offers_v02']
    historical = False
else:
    historical = True
    offers = select_historical_offers(candidate, all_saved_quotes,
        strategy='最近一次報價' if view_mode.startswith('最近') else '歷史最低價')
ranked, summary = rank_rows(candidate, offers, transport, overnight, luggage, direct_only, rank_by)

st.subheader('📅 所有日期 × 已知最低票價')
st.caption(f'目前模式：{view_mode}｜符合日期 {len(candidate)} 組；有價格 {sum(x["lowest_price_twd"] is not None for x in summary)} 組。')
if historical:
    st.warning('這些是過去已觀察到的歷史票價，並非當下可購票價。付款前必須重新查價。')
st.dataframe(pd.DataFrame(summary).rename(columns={
    'departure_date':'去程日','return_date':'回程日','leave_days':'請假天數',
    'leave_dates':'請假日期','lowest_price_twd':'最低已知票價 TWD',
    'total_cost_twd':'總成本 TWD','usable_hours':'可玩小時',
    'price_status':'價格類型','airline':'航空公司','direct':'直飛','source':'來源','flight_rank':'排名'
}), hide_index=True, use_container_width=True)
st.caption('INDICATIVE＝尚未確認回程的參考價；SEARCH_RESULT＝已配對去回程的搜尋結果；TEST＝沙盒報價。')
st.subheader('🏆 航班排名' + ('（歷史，須重新核價）' if historical else '（本次搜尋）'))
if ranked:
    cols=['rank','departure_date','return_date','leave_days','leave_dates','price_twd',
          'total_cost_twd','usable_hours','cost_per_hour','airline','direct','source','mode',
          'observed_at','outbound_departure','outbound_arrival','return_departure','return_arrival']
    st.dataframe(pd.DataFrame(ranked).reindex(columns=cols),hide_index=True,use_container_width=True)
else:
    st.info('目前模式沒有符合條件的報價。可切換至歷史模式，或檢查日期與直飛條件。')

# Create BOTH rankings regardless of which mode is currently selected.
session_ranked, session_summary = rank_rows(candidate, st.session_state['offers_v02'],
    transport, overnight, luggage, direct_only, rank_by)
historic_offers = select_historical_offers(candidate, all_saved_quotes, strategy='歷史最低價')
historic_ranked, historic_summary = rank_rows(candidate, historic_offers,
    transport, overnight, luggage, direct_only, rank_by)
latest_offers = select_historical_offers(candidate, all_saved_quotes, strategy='最近一次報價')
latest_ranked, latest_summary = rank_rows(candidate, latest_offers,
    transport, overnight, luggage, direct_only, rank_by)

st.subheader('📥 下載完整報表')
st.caption('不必重新呼叫 API。Excel 分別列出本次搜尋、歷史最低價、最近一次歷史報價，以及所有原始快照。')
st.download_button('⬇️ 完整 Excel（含歷史排名）',
    data=excel_bytes(session_summary,session_ranked,all_saved_quotes,
        historic_summary=historic_summary,historic_ranked=historic_ranked,
        latest_summary=latest_summary,latest_ranked=latest_ranked),
    file_name='flight_leave_optimizer_v0.6.3.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
a,b=st.columns(2)
a.download_button('⬇️ 所有日期最低票價.csv',data=csv_bytes(summary,SUMMARY_COLUMNS),file_name='all_dates_lowest_prices.csv')
b.download_button('⬇️ 航班排名.csv',data=csv_bytes(ranked,COLUMNS),file_name='flight_rankings.csv',disabled=not bool(ranked))
st.caption('歷史排名顯示的最低價是觀察值，不能視為目前可購報價。')


st.divider()
st.header('💾 v0.6｜歷史資料匯入、備份與還原')
st.caption('舊版 Excel 或 CSV 可匯入；缺少查價時間的資料會標為 LEGACY_UNDATED，不納入 K 線、MACD/RSI 或預測。先預覽，再確認匯入。')
with st.expander('匯入 v0.3–v0.6 Excel／CSV',expanded=False):
    upload=st.file_uploader('選擇 Excel / CSV（航班排名、所有日期摘要或歷史報價快照）',type=['xlsx','csv'],key='historical_import')
    if upload is not None:
        try:
            payload=parse_upload(upload.getvalue(),upload.name,origin,destination)
            st.write(f"識別格式：{payload['type']}｜有效報價：{len(payload['rows'])}｜缺少原始查價時間：{payload['missing_timestamp']}")
            if payload['errors']:st.warning('略過部分無效列：'+'；'.join(payload['errors'][:5]))
            if payload['missing_timestamp']:st.warning('這些舊資料只會保存為缺少歷史時間的匯入資料；不當成過去日期的價格走勢。')
            st.dataframe(pd.DataFrame(payload['rows']).head(30),hide_index=True,use_container_width=True)
            signature=__import__('hashlib').sha256(upload.getvalue()).hexdigest()
            if st.button('確認匯入、合併並去重',type='primary',key='confirm_history_import',disabled=not bool(payload['rows'])):
                count,duplicate=import_quotes(history_db,payload['rows'])
                st.success(f'新增 {count} 筆，略過重複 {duplicate} 筆。下方歷史圖表及 Ollama 將使用合併後的資料。')
                st.rerun()
        except Exception as exc:st.error(f'匯入失敗：{exc}')
with st.expander('匯出 Excel 歷史資料及 SQLite 備份',expanded=False):
    st.download_button('⬇️ 完整歷史 Excel（含 observed_at）',history_excel_bytes(history_db),file_name='flight_history_v0.6.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    # Avoid creating a new backup during every Streamlit rerun.
    if st.button('🗄️ 建立 SQLite 完整備份',key='make_db_backup'):
        try:
            st.session_state['db_backup_download'] = sqlite_backup_bytes(history_db)
            st.success('完整備份已建立，可在下方下載。')
        except Exception as exc:
            st.error(f'備份失敗：{exc}')
    if st.session_state.get('db_backup_download'):
        st.download_button('⬇️ 下載 SQLite 完整備份', data=st.session_state['db_backup_download'],
                           file_name='price_history_backup.sqlite3', mime='application/octet-stream',
                           key='download_db_backup')
with st.expander('⚠️ SQLite 完整還原（將取代目前資料）',expanded=False):
    st.warning('還原前請先下載目前資料庫備份，並停止 Windows 自動排程與其他 Streamlit 執行個體。')
    restore_file=st.file_uploader('上傳先前備份的 SQLite 檔案',type=['sqlite3','db'],key='restore_sqlite')
    if restore_file is not None:
        try:
            raw=restore_file.getvalue();info=validate_backup(raw)
            st.info(f"備份檢查通過：{info['quotes']} 筆報價、{info['insights']} 筆洞察")
            agree=st.checkbox('我確認已停止背景查價、備份目前資料庫，並同意覆蓋目前全部歷史記錄',key='ack_restore')
            if st.button('確認還原 SQLite',disabled=not agree,key='confirm_restore'):
                restored,old=restore_backup(history_db,raw)
                st.session_state['prior_restore_backup']=old
                st.success('還原完成。下方走勢及分析將使用還原後的資料。')
                st.rerun()
        except Exception as exc:st.error(f'備份檔案驗證／還原失敗：{exc}')
    if st.session_state.get('prior_restore_backup'):
        st.download_button('⬇️ 下載本次還原前的自動備份',st.session_state['prior_restore_backup'],file_name='pre_restore.sqlite3')

st.header('📈 歷史機票價格研究｜K 線・MACD・RSI')
st.caption('此區完整保留 v0.5 的歷史折線、K 線、MACD、RSI 與本機 Ollama 分析。')
st.caption('歷史＝本機每次搜尋時保存的報價快照，及來源實際提供的價格洞察；不是可無限制追溯的所有歷史機票成交紀錄。')
with st.expander('🔍 歷史資料與低點總覽', expanded=True):
    past=history_db.quotes(origin,destination)
    insights=history_db.insights(origin,destination)
    trend_rows=analyze_trends(past,insights)
    if trend_rows:
        st.dataframe(pd.DataFrame(trend_rows),use_container_width=True,hide_index=True)
        st.download_button('⬇️ 匯出歷史最低價比較 CSV',pd.DataFrame(trend_rows).to_csv(index=False).encode('utf-8-sig'),file_name='observed_low_prices.csv',mime='text/csv')
    else: st.info('尚無歷史資料。完成 API 搜尋或匯入 CSV 後就會開始累積。')
    st.caption(f'本機已儲存 {len(past)} 筆報價快照、{len(insights)} 筆供應商價格洞察。測試模式不參與趨勢排名。')
    backup=Path(__file__).parent/'data/last_search_snapshot.json'
    if backup.exists() and st.button('匯入舊版 last_search_snapshot.json（缺少原始查價時間）'):
        try:
            imported=json.loads(backup.read_text(encoding='utf-8'))
            payload=parse_upload(pd.DataFrame(imported).to_csv(index=False).encode('utf-8'),'legacy_snapshot.csv',origin,destination)
            count,duplicates=import_quotes(history_db,payload['rows'])
            st.success(f'新增 {count} 筆，跳過 {duplicates} 筆；缺少原始查價時間的資料不會參與技術指標。')
        except Exception as e: st.error(f'舊資料匯入失敗：{e}')
    if insights:
        st.subheader('供應商提供的歷史價格樣本（若有）')
        choices=sorted({(q['departure_date'],q['return_date']) for q in insights})
        chosen=st.selectbox('查看歷史價格洞察的日期組合',choices,format_func=lambda x:f'{x[0]} → {x[1]}',key='price_insights_pair')
        insight_rows=[q for q in insights if (q['departure_date'],q['return_date'])==chosen]
        points=pd.DataFrame([{'date':x['history_time'],'price_twd':x['history_price_twd']} for x in insight_rows if x['history_time'] and x['history_price_twd']])
        if not points.empty:
            points['date']=pd.to_datetime(points['date'],utc=True)
            st.line_chart(points.drop_duplicates(['date','price_twd']).set_index('date')['price_twd'])
            st.caption('這是供應商回傳的歷史樣本，不是本機實際觀察到的每日報價；不和本機快照 K 線混合。')
        else:
            st.info('供應商未提供這組日期的歷史樣本（可能只有 typical range / price level）。')


if past:
    route_pairs=sorted({(x['departure_date'],x['return_date']) for x in past if x.get('mode')!='TEST'})
    if route_pairs:
        dep,ret=st.selectbox('要分析哪一組固定來回日期',route_pairs,
            format_func=lambda x:f'{x[0]} → {x[1]}')
        pair_rows=[r for r in past if r['departure_date']==dep and r['return_date']==ret and r['mode']!='TEST']
        source_modes=sorted({(r['source'],r['mode']) for r in pair_rows})
        provider,price_mode=st.selectbox('比較同一來源、同一價格類型（避免混合不可比資料）',source_modes,
            format_func=lambda x:f'{x[0]} / {x[1]}')
        df=technical_indicators(observed_series(past,dep,ret,provider,price_mode))
        stats=price_stats(df)
        if stats:
            x,y,z=st.columns(3)
            x.metric('最新觀察價（TWD）',f"{stats['latest_twd']:,}")
            y.metric('歷史觀察最低（TWD）',f"{stats['observed_low_twd']:,}")
            z.metric('相對觀察中位數',f"{stats['vs_median_pct']:+.1f}%")
            st.caption(f"實際有資料的日期：{stats['observations_days']} 天；最新觀察日 {stats['last_seen']}。這只代表本機已看過的價格，不能保證是市場歷史低點。")
            chart_style=st.radio('歷史走勢圖', ['報價折線','觀察快照 K 線'],horizontal=True)
            fig=make_subplots(rows=3,cols=1,shared_xaxes=True,vertical_spacing=0.045,row_heights=[0.57,0.24,0.19],
                subplot_titles=('機票報價（TWD）','MACD(12,26,9)','RSI(14)'))
            if chart_style=='觀察快照 K 線':
                fig.add_trace(go.Candlestick(x=df['date'],open=df['open'],high=df['high'],low=df['low'],close=df['close'],name='觀察 OHLC'),row=1,col=1)
            else:
                fig.add_trace(go.Scatter(x=df['date'],y=df['close'],mode='lines+markers',name='每日最新觀察價'),row=1,col=1)
            for field,name in [('ema12','EMA 12'),('ema26','EMA 26')]:
                if df[field].notna().any(): fig.add_trace(go.Scatter(x=df['date'],y=df[field],name=name,mode='lines'),row=1,col=1)
            for field,name in [('macd','MACD'),('signal','訊號線')]:
                fig.add_trace(go.Scatter(x=df['date'],y=df[field],name=name),row=2,col=1)
            fig.add_trace(go.Bar(x=df['date'],y=df['histogram'],name='MACD 柱'),row=2,col=1)
            fig.add_trace(go.Scatter(x=df['date'],y=df['rsi14'],name='RSI 14'),row=3,col=1)
            fig.add_hline(y=30,line_dash='dot',row=3,col=1)
            fig.add_hline(y=70,line_dash='dot',row=3,col=1)
            fig.update_layout(height=750,legend=dict(orientation='h',y=-0.14),xaxis_rangeslider_visible=False,margin=dict(t=68,l=32,r=20,b=65))
            st.plotly_chart(fig,use_container_width=True)
            st.caption('K 線是一天內「被查詢到的最低報價」所形成的觀察 OHLC，非股票成交價。每日只有一筆快照時開高低收相同；缺少資料不補假價格。MACD 至少約 34 個不同觀察日，RSI 約 15 日才較有意義；不保證能預測機票跌價。')
            st.dataframe(df,use_container_width=True,hide_index=True)
            st.download_button('⬇️ 歷史價格與技術指標 CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name=f'flight_history_{dep}_{ret}.csv',mime='text/csv')
            st.subheader('🤖 本機 Ollama 分析')
            st.caption('資料只傳送至本機 Ollama 服務（127.0.0.1:11434），不會將 SerpApi Key 提供給模型。')
            model_name=st.text_input('本機模型名稱（例如 llama3）','llama3')
            if st.button('用 Ollama 分析歷史票價'):
                try:
                    with st.spinner('正在由本機 Ollama 生成分析…'):
                        answer=explain(stats,df[['date','close','macd','signal','rsi14']].tail(80).to_dict('records'),model=model_name)
                    st.markdown(answer)
                except Exception as e:
                    st.error(f'本機 Ollama 無法完成分析：{e}。請確認 ollama serve 正在執行，且已下載指定模型。')
        else:st.warning('這組日期沒有可分析的非測試報價。')

st.subheader('🔎 歷史價格搜尋與限制')
st.markdown("""- 可以：從現在起自動保存每次 API 搜尋的機票報價；利用有提供價格歷史的資料來源補充其回傳的歷史樣本。
- 不能保證：免費 API 能回溯任意日期的完整舊票價、交易成交價、庫存或所有航空公司的最低價。
- 比較低點時請固定 **相同去回程日期、相同來源、相同票價類型**。其他出發日價格便宜，不等於同一張機票正在跌價。""")


st.divider()
st.header('⏰ v0.5｜無人值守排程與買票時機研究')
st.caption('Windows 工作排程器在背景執行 automation.py；Streamlit 關閉後仍能保存報價。電腦必須保持開機、連網，並符合工作排程器的登入／喚醒設定。')
config=load_config()
with st.expander('設定早晚自動查價條件',expanded=False):
    x,y=st.columns(2)
    c_origin=x.text_input('監控出發機場',config['origin'],key='monitor_origin').upper()
    c_destination=y.text_input('監控目的地機場',config['destination'],key='monitor_destination').upper()
    a,b=st.columns(2)
    c_start=a.date_input('監控最早出發',value=date.fromisoformat(config['earliest_departure']),key='monitor_start')
    c_end=b.date_input('監控最晚回程',value=date.fromisoformat(config['latest_return']),key='monitor_end')
    c_days=st.number_input('固定旅行天數',2,30,int(config['trip_days']),key='monitor_days')
    a,b=st.columns(2)
    c_min=a.number_input('最少請假天數',0,15,int(config['min_leave']),key='monitor_min_leave')
    c_max=b.number_input('最多請假天數',0,15,int(config['max_leave']),key='monitor_max_leave')
    a,b=st.columns(2)
    c_limit=a.number_input('每次最多查詢日期組數',1,100,int(config['max_searches_per_run']))
    c_daily=b.number_input('每日最多 API 初次查詢次數',1,500,int(config['daily_run_limit']))
    c_confirm=st.checkbox('自動排程精查回程（額外 API 呼叫；首次建議不選）',value=bool(config['confirm_return']))
    c_threshold=st.number_input('低價提醒門檻 TWD',0,200000,int(config['alerts_below_twd']),100)
    if st.button('儲存排程設定',type='primary'):
        if c_min>c_max or c_start>c_end:
            st.error('請檢查日期與請假天數上下限。')
        else:
            config.update(origin=c_origin,destination=c_destination,earliest_departure=c_start.isoformat(),
                latest_return=c_end.isoformat(),trip_days=int(c_days),min_leave=int(c_min),max_leave=int(c_max),
                max_searches_per_run=int(c_limit),daily_run_limit=int(c_daily),confirm_return=bool(c_confirm),alerts_below_twd=int(c_threshold))
            CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
            st.success('監控條件已存入 data/monitor_config.json。若要讓排程生效，仍需執行 INSTALL_SCHEDULE.ps1。')
st.markdown('**排程啟用：** 在專案資料夾的 PowerShell 執行 `powershell -ExecutionPolicy Bypass -File .\\INSTALL_SCHEDULE.ps1`，預設每天 08:00 / 20:00。請將 SerpApi Key 存入僅供本機使用的 `data/serpapi_key.txt`（單行），該檔案已排除 Git 追蹤。')
st.markdown('**手動測試：** `python automation.py --dry-run`（不耗 API）或 `python automation.py`（真實查價）；結果在 `data/monitor_log.jsonl`。排程不會自動寄信；低價提醒會寫在 `data/latest_alerts.txt`。')
logfile=Path(__file__).parent/'data/monitor_log.jsonl'
if logfile.exists():
    try:
        lines=logfile.read_text(encoding='utf-8').splitlines()[-30:]
        runs=[json.loads(line) for line in lines if line.strip()]
        st.dataframe(pd.DataFrame([{'查詢時間':q.get('checked_at'),'日期組數':q.get('total_candidates'),'實際查詢':q.get('attempted'),'已儲存':q.get('saved'),'錯誤':len(q.get('errors',[])),'低價提醒':len(q.get('alerts',[]))} for q in reversed(runs)]),hide_index=True,use_container_width=True)
    except Exception as exc:st.warning(f'無法讀取監控紀錄：{exc}')

st.subheader('🔮 固定來回日期：未來 7 日價格情境預測')
st.caption('只針對已配對來回行程的 SEARCH_RESULT 等報價建立同質時間序列。至少 7 個不同觀察日且橫跨 7 天；這是低信心的統計情境，不是保證會出現的未來最低價。')
rows=history_db.quotes(origin,destination)
groups=sorted({(r['departure_date'],r['return_date'],r['source'],r['mode']) for r in rows if r['mode'] not in ('TEST','INDICATIVE','UNKNOWN','LEGACY_UNDATED')})
if not groups:st.info('尚未累積已配對的來回報價；先使用完整回程確認功能，並持續數日查價。')
else:
    group=st.selectbox('選擇固定行程及同類型報價',groups,format_func=lambda z:f'{z[0]} → {z[1]}｜{z[2]}｜{z[3]}',key='forecast_group')
    series=daily_lows(rows,group[0],group[1],group[2],group[3])
    result=project_price(series,group[0])
    if result['status']=='EXPLORATORY':
        a,b,c=st.columns(3)
        a.metric('最近觀察最低價',f"NT${result['latest_twd']:,}")
        b.metric(f"{result['forecast_days']} 天後情境中位價",f"NT${result['scenario_price_twd']:,}")
        c.metric('情境範圍',f"NT${result['scenario_low_twd']:,}–{result['scenario_high_twd']:,}")
        st.info(result['advice'])
        st.caption(f"{result['observations']} 個不同報價日；可信度：{result['confidence']}。{result['reason']}")
    else:st.warning(f"{result.get('reason','無法預估')}｜樣本數：{result.get('observations',0)}")
    if series:
        st.line_chart(pd.DataFrame(series,columns=['日期','票價']).set_index('日期')['票價'])
    if st.button('使用 llama3 解釋這組預測（不讓 AI 虛構報價）'):
        from ollama_analysis import explain as ollama_explain
        try:
            text_out=ollama_explain({'scenario':result,'observed_price_points':len(series),'warning':'機票歷史快照，不代表未來保證低點'},[{'date':str(d),'close':v} for d,v in series[-30:]],model='llama3')
            st.markdown(text_out)
        except Exception as exc:st.error(str(exc))
