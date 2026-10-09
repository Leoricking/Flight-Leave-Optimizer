import io, sqlite3
import pandas as pd
import pytest
from history import PriceHistory
from history_io import parse_upload,import_quotes,sqlite_backup_bytes,restore_backup,validate_backup,history_excel_bytes
from analytics import observed_series

def test_csv_import_dedup_and_no_synthetic_history(tmp_path):
 db=PriceHistory(tmp_path/'price.sqlite3')
 csv=b'departure_date,return_date,price_twd,airline,source\n2026-10-31,2026-11-04,8098,Scoot,Google Flights\n'
 p=parse_upload(csv,'ranking.csv');assert p['missing_timestamp']==1
 assert import_quotes(db,p['rows'])==(1,0)
 assert import_quotes(db,parse_upload(csv,'ranking.csv')['rows'])==(0,1)
 assert len(db.quotes())==1
 assert observed_series(db.quotes(),'2026-10-31','2026-11-04').empty

def test_original_timestamp_and_workbook_roundtrip(tmp_path):
 db=PriceHistory(tmp_path/'price.sqlite3')
 csv=b'observed_at,origin,destination,departure_date,return_date,price_twd,airline,source,mode,direct\n2026-10-09T10:00:00+08:00,TPE,CTS,2026-10-31,2026-11-04,8098,Scoot,SerpApi,SEARCH_RESULT,1\n'
 p=parse_upload(csv,'history.csv');assert p['missing_timestamp']==0
 assert import_quotes(db,p['rows'])==(1,0)
 assert db.quotes()[0]['observed_at'].startswith('2026-10-09T02:00')
 xlsx=history_excel_bytes(db)
 q=parse_upload(xlsx,'myhistory.xlsx');assert q['type']=='history'
 assert import_quotes(db,q['rows'])==(0,1)

def test_ranking_and_summary_workbook(tmp_path):
 out=io.BytesIO()
 with pd.ExcelWriter(out,engine='xlsxwriter') as w:
  pd.DataFrame([{'departure_date':'2026-10-31','return_date':'2026-11-04','lowest_price_twd':8098}]).to_excel(w,'所有日期最低票價',index=False)
  pd.DataFrame([{'departure_date':'2026-10-31','return_date':'2026-11-04','price_twd':8098,'checked_at':'2026-10-09T10:00:00+08:00'}]).to_excel(w,'航班排名',index=False)
 p=parse_upload(out.getvalue(),'report.xlsx')
 assert p['type']=='ranking' and len(p['rows'])==1 and p['missing_timestamp']==0

def test_sqlite_backup_validate_restore(tmp_path):
 db=PriceHistory(tmp_path/'price.sqlite3')
 raw=sqlite_backup_bytes(db)
 assert validate_backup(raw)['quotes']==0
 p=parse_upload(b'departure_date,return_date,price_twd\n2026-10-31,2026-11-04,8098\n','ranking.csv')
 import_quotes(db,p['rows']);assert len(db.quotes())==1
 stats,previous=restore_backup(db,raw)
 assert stats['quotes']==0 and len(db.quotes())==0
 assert validate_backup(previous)['quotes']==1
 with pytest.raises(ValueError):validate_backup(b'garbage')
