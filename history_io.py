"""v0.6: format-aware historical quote import/export and safe SQLite backup."""
from __future__ import annotations
import hashlib
import io
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from history import PriceHistory

HISTORY_COLS = ['observed_at','origin','destination','departure_date','return_date','price_twd','airline','source','mode','direct','outbound_departure','outbound_arrival','return_departure','return_arrival']
DATE_SUMMARY = '所有日期最低票價'
RANKINGS = '航班排名'
HISTORY = '歷史報價快照'


def _clean(v):
    if v is None or pd.isna(v): return None
    return str(v).strip()


def _date(v):
    s=_clean(v)
    if not s: return None
    try: return pd.to_datetime(s, errors='raise').strftime('%Y-%m-%d')
    except (ValueError,TypeError,OverflowError):return None


def _timestamp(v):
    s=_clean(v)
    if not s: return None
    try:
        d=pd.Timestamp(s)
        if pd.isna(d):return None
        if d.tzinfo is None: d=d.tz_localize('Asia/Taipei')
        return d.tz_convert('UTC').isoformat()
    except (ValueError,TypeError,OverflowError):return None


def _truth(v):
    s=str(v).strip().lower()
    if s in ('1','1.0','true','yes','y','是','直飛'):return True
    if s in ('0','0.0','false','no','n','否','轉機'):return False
    return None


def _format(df, name):
    fields=set(str(c).lower().strip() for c in df.columns)
    if {'departure_date','return_date','price_twd'} <= fields:
        return 'history' if 'observed_at' in fields else 'ranking'
    if {'departure_date','return_date','lowest_price_twd'} <= fields:return 'summary'
    if 'date' in fields and {'close','open'} <= fields:return 'indicator'
    raise ValueError(f'{name}: 無法辨識欄位；至少需 departure_date、return_date 和 price_twd 或 lowest_price_twd')


def parse_upload(file_bytes, filename, fallback_origin='TPE', fallback_destination='CTS'):
    """Produce preview; imports from legacy exports are transparently labelled LEGACY_UNDATED."""
    ext=Path(filename).suffix.lower()
    if ext=='.xlsx':
        excel=pd.ExcelFile(io.BytesIO(file_bytes))
        sheets={n:pd.read_excel(excel,sheet_name=n,dtype=object) for n in excel.sheet_names}
    elif ext=='.csv':
        sheets={Path(filename).stem:pd.read_csv(io.BytesIO(file_bytes),dtype=object,encoding='utf-8-sig')}
    else:raise ValueError('只支援 .xlsx 或 .csv')
    chosen=[]
    for name,df in sheets.items():
        df.columns=[str(c).strip().lower() for c in df.columns]
        try: kind=_format(df,name)
        except ValueError:continue
        if kind=='indicator':continue
        chosen.append((name,kind,df))
    if not chosen:raise ValueError('沒有可匯入的航班報價欄位，無法從圖表或純價格指標推導原始行程。')
    # Prefer complete historical observations; otherwise rankings, then summaries; never double import summary+rankings.
    preferred=min(('history','ranking','summary'), key=lambda t:next((0 for _,k,_ in chosen if k==t),1))
    if any(k=='history' for _,k,_ in chosen):preferred='history'
    elif any(k=='ranking' for _,k,_ in chosen):preferred='ranking'
    else:preferred='summary'
    selected=[(n,k,d) for n,k,d in chosen if k==preferred]
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    output=[];errors=[]
    for name,kind,frame in selected:
        for idx,row in enumerate(frame.to_dict('records'),2):
            dep=_date(row.get('departure_date'));ret=_date(row.get('return_date'))
            value=row.get('price_twd') if kind!='summary' else row.get('lowest_price_twd')
            try:price=float(str(value).replace(',',''))
            except (TypeError,ValueError):continue  # unpriced calendar candidates are not quotes
            if not dep or not ret or not (0 < price < 1e8):errors.append(f'{name} 第{idx}列：日期或價格無效');continue
            observed=_timestamp(row.get('observed_at')) or _timestamp(row.get('checked_at'))
            undated=not observed
            origin=_clean(row.get('origin')) or fallback_origin
            destination=_clean(row.get('destination')) or fallback_destination
            source=_clean(row.get('source')) or 'LEGACY_IMPORT'
            mode=_clean(row.get('mode')) or _clean(row.get('price_status')) or 'MANUAL'
            if undated:mode='LEGACY_UNDATED'
            if kind=='summary' and mode=='未取得':continue
            output.append({
                'observed_at':observed or now,'origin':origin,'destination':destination,
                'departure_date':dep,'return_date':ret,'price_twd':price,
                'airline':_clean(row.get('airline')) or '', 'source':source,'mode':mode,
                'direct':_truth(row.get('direct')),
                **{c:_clean(row.get(c)) or '' for c in ('outbound_departure','outbound_arrival','return_departure','return_arrival')},
                'time_quality':'import_time_only' if undated else 'source_timestamp',
                'import_sheet':name,
            })
    return {'rows':output,'errors':errors,'type':preferred,'sheet_names':[n for n,_,_ in selected],
            'missing_timestamp':sum(x['time_quality']=='import_time_only' for x in output)}


def _quote_key(r):
    fields=['observed_at','origin','destination','departure_date','return_date','price_twd','airline','source','mode','direct','outbound_departure','outbound_arrival','return_departure','return_arrival']
    # normalize timestamps across timezone repr, and treat NULL direct consistently
    pieces=[str(r.get(k) if r.get(k) is not None else '') for k in fields]
    pieces[0]='LEGACY_UNDATED' if r.get('mode')=='LEGACY_UNDATED' else (_timestamp(pieces[0]) or pieces[0])
    pieces[5]=str(round(float(r['price_twd']),4))
    pieces[9]='' if r.get('direct') is None else ('1' if _truth(r.get('direct')) else '0')
    return hashlib.sha256('\x1f'.join(pieces).encode()).hexdigest()


def import_quotes(db:PriceHistory,rows):
    """Idempotent import of a single batch; preserves original observed_at and route."""
    inserted=0;duplicates=0
    with db._connect() as con:
        con.row_factory=sqlite3.Row
        prior={_quote_key(dict(r)) for r in con.execute('SELECT '+','.join(HISTORY_COLS)+' FROM quote_snapshots')}
        for row in rows:
            key=_quote_key(row)
            if key in prior:duplicates+=1;continue
            # Save explicit origin + destination and observation datetime; do not overwrite with UI route.
            vals=[row.get(k) for k in HISTORY_COLS]
            vals[HISTORY_COLS.index('direct')]=None if row.get('direct') is None else int(bool(row['direct']))
            import json
            con.execute('''INSERT INTO quote_snapshots(observed_at,origin,destination,departure_date,return_date,price_twd,airline,source,mode,direct,outbound_departure,outbound_arrival,return_departure,return_arrival,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals+[json.dumps(row,ensure_ascii=False,default=str)])
            inserted+=1;prior.add(key)
    return inserted,duplicates


def history_excel_bytes(db:PriceHistory):
    rows=db.quotes();insights=db.insights()
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine='xlsxwriter') as writer:
        for sheet,data,columns in [(HISTORY,rows,HISTORY_COLS),('供應商價格洞察',insights,None)]:
            df=pd.DataFrame(data).reindex(columns=columns) if columns else pd.DataFrame(data)
            df.to_excel(writer,sheet_name=sheet,index=False)
            ws=writer.sheets[sheet]
            ws.freeze_panes(1,0)
            ws.set_column(0,max(0,len(df.columns)-1),22)
        pd.DataFrame({'說明':['歷史報價快照的 observed_at 是每筆報價的原始查詢時間（UTC 或含時區）。','LEGACY_UNDATED 表示舊版匯出缺少原始查詢時間；此資料不參與 K 線與預測。','供應商價格洞察與本機實際查價快照不混合。']}).to_excel(writer,sheet_name='資料說明',index=False)
    return out.getvalue()


def sqlite_backup_bytes(db: PriceHistory):
    """Return an atomic SQLite backup without a Windows-locked temporary file.

    sqlite3 backup transfers a consistent snapshot into a memory database;
    serialize returns the actual database bytes. Connections are closed
    before returning to Streamlit.
    """
    with sqlite3.connect(str(db.path), timeout=30) as source:
        with sqlite3.connect(':memory:') as snapshot:
            source.backup(snapshot)
            return snapshot.serialize()


def validate_backup(raw: bytes):
    if len(raw) > 300_000_000:
        raise ValueError('備份檔案超過 300MB，請先使用離線備份工具。')
    if not raw.startswith(b'SQLite format 3\x00'):
        raise ValueError('不是 SQLite 資料庫。')
    # No filesystem temp files: deserialize only into a private in-memory DB.
    with sqlite3.connect(':memory:') as con:
        try:
            con.deserialize(raw)
            result = con.execute('PRAGMA integrity_check').fetchone()[0]
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            cols = {r[1] for r in con.execute('PRAGMA table_info(quote_snapshots)')} if 'quote_snapshots' in tables else set()
            if result != 'ok' or not {'quote_snapshots', 'price_insights'} <= tables or not set(HISTORY_COLS) <= cols:
                raise ValueError('SQLite 備份不完整或資料結構不相容。')
            return {'quotes': con.execute('SELECT COUNT(*) FROM quote_snapshots').fetchone()[0],
                    'insights': con.execute('SELECT COUNT(*) FROM price_insights').fetchone()[0]}
        except sqlite3.DatabaseError as ex:
            raise ValueError('SQLite 備份檔案損毀或格式不支援。') from ex


def restore_backup(db: PriceHistory, raw: bytes):
    """Validate and restore an entire backup, preserving an in-memory rollback."""
    stats = validate_backup(raw)
    old_backup = sqlite_backup_bytes(db)
    try:
        with sqlite3.connect(':memory:') as source:
            source.deserialize(raw)
            with sqlite3.connect(str(db.path), timeout=30) as destination:
                source.backup(destination)
    except Exception:
        with sqlite3.connect(':memory:') as rollback:
            rollback.deserialize(old_backup)
            with sqlite3.connect(str(db.path), timeout=30) as destination:
                rollback.backup(destination)
        raise
    return stats, old_backup
