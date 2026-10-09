from __future__ import annotations
import os, csv, json, time
from datetime import date
from pathlib import Path
import streamlit as st
import pandas as pd
from core import generate,holiday_set,manual_csv,join_offers
from providers import duffel_search
from report import export_csv,export_xlsx

st.set_page_config(page_title='Flight Leave Optimizer',page_icon='✈️',layout='wide')
st.title('✈️ Flight Leave Optimizer')
st.caption('竹南出發｜航空票價 × 請假日期 × 目的地可用時間｜不混淆測試與真實價格')
with st.sidebar:
    st.header('搜尋條件')
    c1,c2=st.columns(2)
    origin=c1.text_input('出發機場','TPE').upper().strip()
    destination=c2.text_input('目的地機場','CTS').upper().strip()
    start=st.date_input('最早出發日',value=date(2026,10,20))
    end=st.date_input('最晚回程日',value=date(2026,11,16))
    days=st.number_input('行程天數（含飛行日）',min_value=2,max_value=30,value=5)
    leaves=st.number_input('最多請假天數',min_value=0,max_value=15,value=2)
    direct_only=st.checkbox('只顯示直飛',value=True)
    st.markdown('**地面交通及附加成本（自行調整）**')
    transport=st.number_input('竹南 ⇄ 桃機交通 TWD',0,20000,1200,100)
    overnight=st.number_input('機場過夜／住宿 TWD',0,20000,0,100)
    luggage=st.number_input('行李追加成本 TWD',0,20000,0,100)
    st.caption('地面交通價格為使用者設定的預算，不是即時報價。')

try: candidate=generate(start,end,int(days),int(leaves),holiday_set())
except Exception as e: st.error(str(e));st.stop()
st.metric('符合請假條件的日期組合',len(candidate))
with st.expander('查看所有合法請假組合',expanded=False): st.dataframe(pd.DataFrame(candidate),use_container_width=True,hide_index=True)

mode=st.radio('票價資料來源',['手動匯入 CSV','Duffel API 即時查詢'],horizontal=True)
if mode=='手動匯入 CSV':
    st.info('匯入 Trip.com／Skyscanner／Google Flights 等自行確認的報價。未匯入時不會顯示虛構票價。')
    upload=st.file_uploader('上傳 CSV（UTF-8）',type=['csv'])
    st.download_button('下載空白 CSV 模板',data='departure_date,return_date,price_twd,airline,direct,outbound_departure,outbound_arrival,return_departure,return_arrival,source\n',file_name='offers_template.csv',mime='text/csv')
    if upload:
        p=Path('data/uploaded_offers.csv');p.parent.mkdir(exist_ok=True)
        p.write_bytes(upload.getvalue())
        try: st.session_state['offers']=list(manual_csv(p))
        except Exception as e: st.error(f'CSV 讀取失敗：{e}')
else:
    token=st.text_input('Duffel Access Token（或以 DUFFEL_ACCESS_TOKEN 環境變數設定）',type='password',placeholder='duffel_live_... / duffel_test_...') or os.environ.get('DUFFEL_ACCESS_TOKEN','')
    limit=st.number_input('本次查詢幾組日期（避免 API 額度過量）',1,max(1,len(candidate)),min(5,max(1,len(candidate))))
    pause=st.slider('查詢間隔（秒）',0.5,5.0,1.5,0.5)
    st.warning('API 搜尋需要有效金鑰與帳號權限。TEST 模式結果只是沙盒資料，不能當可購買的即時票價。')
    if st.button('開始 API 查價',type='primary',disabled=not candidate):
        if not token: st.error('請先輸入 Duffel API Token。')
        else:
            all_offers=[];failed=[];progress=st.progress(0)
            for idx,d in enumerate(candidate[:int(limit)]):
                try:
                    found=duffel_search(origin,destination,d['departure_date'],d['return_date'],token)
                    all_offers.extend(found)
                except Exception as e: failed.append(f"{d['departure_date']} ~ {d['return_date']}: {e}")
                progress.progress((idx+1)/int(limit))
                if idx+1<int(limit):time.sleep(pause)
            st.session_state['offers']=all_offers
            st.success(f'完成 {limit} 組查詢，取得 {len(all_offers)} 筆報價；失敗 {len(failed)} 組。')
            if failed:st.error('\n'.join(failed[:8]))
            # Keep snapshots separated from active results; never regard expired results as live.
            if all_offers:
                p=Path('data/last_api_snapshot.json');p.parent.mkdir(exist_ok=True)
                p.write_text(json.dumps(all_offers,ensure_ascii=False,indent=2),encoding='utf-8')

result=join_offers(candidate,st.session_state.get('offers',[]),transport,overnight,luggage,direct_only)
st.subheader('排名結果')
if not result: st.info('沒有符合條件的報價。請匯入 CSV、執行 API 查詢，或取消「只顯示直飛」。')
else:
    st.success(f'符合條件的航班共 {len(result)} 筆；排序依總成本，次要比較可用時間。')
    if any(r.get('mode')=='TEST' for r in result):st.warning('結果包含 Duffel TEST 模式報價，請勿拿它當作實際票價。')
    show=['departure_date','return_date','leave_days','leave_dates','price_twd','total_cost_twd','usable_hours','cost_per_hour','airline','direct','source','mode']
    st.dataframe(pd.DataFrame(result)[show],hide_index=True,use_container_width=True)
    if any(r.get('usable_hours') for r in result):
        st.subheader('每小時旅行成本最低')
        ranked=sorted([r for r in result if r.get('cost_per_hour') is not None],key=lambda r:r['cost_per_hour'])
        if ranked:st.dataframe(pd.DataFrame(ranked)[show].head(10),hide_index=True,use_container_width=True)
    if st.button('產生 CSV + Excel 報表'):
        try:
            export_csv(result,'data/flight_rankings.csv')
            export_xlsx(result,'data/flight_rankings.xlsx')
            st.success('報表已建立，可於下方下載。')
        except Exception as e:st.error(f'匯出失敗：{e}')
    for filename,mime in [('data/flight_rankings.csv','text/csv'),('data/flight_rankings.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]:
        if Path(filename).exists():
            st.download_button('下載 '+Path(filename).suffix.upper(),data=Path(filename).read_bytes(),file_name=Path(filename).name,mime=mime)
    st.caption('票價可能過期；實際付款前請重新驗價。行李及地面交通成本目前由使用者自行輸入。')
