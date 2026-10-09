"""Portable CSV/XLSX reporting (no artifact_tool runtime dependency)."""
from __future__ import annotations
import csv
from pathlib import Path
from io import BytesIO, StringIO
import pandas as pd

COLUMNS = ['rank','departure_date','return_date','leave_days','leave_dates','price_twd','total_cost_twd','usable_hours','cost_per_hour','airline','direct','source','mode','outbound_departure','outbound_arrival','return_departure','return_arrival','checked_at','expires_at','offer_id']
SUMMARY_COLUMNS = ['departure_date','return_date','leave_days','leave_dates','lowest_price_twd','total_cost_twd','usable_hours','price_status','airline','direct','source','flight_rank']

def make_summary(candidates, ranked):
    """Exactly one row per feasible date pair. Price is minimum among known offers."""
    by_date = {}
    ranks = {}
    for i, offer in enumerate(ranked, 1):
        key = (offer['departure_date'], offer['return_date'])
        if key not in by_date or float(offer['price_twd']) < float(by_date[key]['price_twd']):
            by_date[key] = offer
        ranks.setdefault(key, i)
    rows=[]
    for d in candidates:
        key=(d['departure_date'], d['return_date'])
        best=by_date.get(key)
        rows.append({
            **{k:d.get(k,'') for k in SUMMARY_COLUMNS if k in d},
            'lowest_price_twd':best.get('price_twd') if best else None,
            'total_cost_twd':best.get('total_cost_twd') if best else None,
            'usable_hours':best.get('usable_hours') if best else None,
            'price_status':best.get('mode','未取得') if best else '未取得',
            'airline':best.get('airline','') if best else '',
            'direct':best.get('direct') if best else None,
            'source':best.get('source','') if best else '',
            'flight_rank':ranks.get(key),
        })
    return rows

def add_ranks(rows):
    return [dict(row,rank=i) for i,row in enumerate(rows,1)]

def csv_bytes(rows, columns):
    stream=StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore')
    writer.writeheader();writer.writerows(rows)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')

def export_csv(rows,path,columns=COLUMNS):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(csv_bytes(rows,columns))
    return path

def excel_bytes(summary, ranked, history_quotes=None):
    """Create 2 styled Excel sheets suitable for regular pip-based Windows installs."""
    out=BytesIO()
    with pd.ExcelWriter(out,engine='xlsxwriter',datetime_format='yyyy-mm-dd hh:mm',engine_kwargs={'options':{'strings_to_urls':False}}) as writer:
        specs=[('所有日期最低票價',summary,SUMMARY_COLUMNS),('航班排名',ranked,COLUMNS)]
        for sheet,rows,cols in specs:
            df=pd.DataFrame(rows).reindex(columns=cols)
            df=df.where(pd.notna(df),'')
            df.to_excel(writer,sheet_name=sheet,index=False)
            book=writer.book; ws=writer.sheets[sheet]
            header=book.add_format({'bold':True,'font_color':'white','bg_color':'#17447D','text_wrap':True,'valign':'vcenter','border':0})
            money=book.add_format({'num_format':'#,##0','align':'right'})
            decimal=book.add_format({'num_format':'0.0','align':'right'})
            for i,col in enumerate(cols):
                ws.write(0,i,col,header)
                width=32 if col in ('leave_dates','source','airline') else (23 if 'departure' in col or 'arrival' in col else 18)
                ws.set_column(i,i,width,money if col in ('lowest_price_twd','price_twd','total_cost_twd') else decimal if col in ('usable_hours','cost_per_hour') else None)
            ws.set_row(0,34)
            ws.freeze_panes(1,0)
            if len(df):
                ws.autofilter(0,0,len(df),len(cols)-1)
                if 'price_status' in cols:
                    j=cols.index('price_status')
                    warn=book.add_format({'bg_color':'#FFF2D9','font_color':'#7A4E00'})
                    ws.conditional_format(1,j,len(df),j,{'type':'text','criteria':'containing','value':'未取得','format':warn})
                if 'rank' in cols:
                    j=cols.index('rank')
                    best=book.add_format({'bg_color':'#DFF1E4','font_color':'#18643A','bold':True})
                    ws.conditional_format(1,j,len(df),j,{'type':'cell','criteria':'<=','value':3,'format':best})
        if history_quotes is not None:
            from history_io import HISTORY_COLS
            historic=pd.DataFrame(history_quotes).reindex(columns=HISTORY_COLS)
            historic.to_excel(writer,sheet_name='歷史報價快照',index=False)
            ws=writer.sheets['歷史報價快照'];ws.freeze_panes(1,0)
            ws.set_column(0,0,29);ws.set_column(1,len(HISTORY_COLS)-1,22)
        meta=book.add_worksheet('報表說明')
        meta.set_column('A:A',26);meta.set_column('B:B',104)
        instructions=[('報表','Flight Leave Optimizer v0.3'),('所有日期最低票價','每個符合請假條件的日期組合都會保留；沒有資料時顯示「未取得」。'),('航班排名','依主畫面所選排序規則排名，包含所有已取得的航班報價。'),('INDICATIVE','搜尋參考價格，尚未確認完整去回程航班。'),('SEARCH_RESULT','已配對去回程的搜尋結果；付款前仍需驗證票價與座位。'),('TEST','沙盒測試價格，不是真實可購價格。'),('MANUAL','由使用者自行輸入或匯入的報價。'),('最低價','「所有日期最低票價」依票價選最低，與依其他規則排列的「航班排名」可能不同。')]
        for n,(a,b) in enumerate(instructions):meta.write(n,0,a);meta.write(n,1,b)
    return out.getvalue()

def export_xlsx(rows,path,summary=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(excel_bytes(summary if summary is not None else [],add_ranks(rows)))
    return path
