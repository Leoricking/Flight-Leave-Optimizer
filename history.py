"""Persistent observed quotes and optional provider price-insight history.

Historical points are descriptive observations, not verified ticket transactions.
No API is required to examine saved observations.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
import json, sqlite3
from contextlib import contextmanager

SCHEMA = '''
CREATE TABLE IF NOT EXISTS quote_snapshots (
 id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, origin TEXT NOT NULL,
 destination TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL,
 price_twd REAL NOT NULL CHECK(price_twd>0), airline TEXT,
 source TEXT NOT NULL, mode TEXT NOT NULL, direct INTEGER,
 outbound_departure TEXT, outbound_arrival TEXT, return_departure TEXT, return_arrival TEXT,
 raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_route_dates ON quote_snapshots(origin,destination,departure_date,return_date,observed_at);
CREATE TABLE IF NOT EXISTS price_insights (
 id INTEGER PRIMARY KEY, retrieved_at TEXT NOT NULL, origin TEXT NOT NULL,
 destination TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL,
 price_level TEXT, typical_low_twd REAL, typical_high_twd REAL,
 history_time TEXT, history_price_twd REAL, source TEXT NOT NULL,
 UNIQUE(origin,destination,departure_date,return_date,history_time,source)
);
'''

class PriceHistory:
 def __init__(self,path='data/price_history.sqlite3'):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self._connect() as con:con.executescript(SCHEMA)
 @contextmanager
 def _connect(self):
  con=sqlite3.connect(self.path)
  try:
   yield con
   con.commit()
  finally:
   con.close()
 def save_offers(self,origin,destination,offers,observed_at=None):
  observed_at=observed_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
  entries=[]
  for r in offers:
   try:price=float(r['price_twd'])
   except (KeyError,TypeError,ValueError):continue
   if price<=0 or not r.get('departure_date') or not r.get('return_date'):continue
   entries.append((observed_at,origin,destination,r['departure_date'],r['return_date'],price,
    r.get('airline',''),r.get('source','UNKNOWN'),r.get('mode','UNKNOWN'),
    None if r.get('direct') is None else int(bool(r['direct'])),
    r.get('outbound_departure',''),r.get('outbound_arrival',''),r.get('return_departure',''),r.get('return_arrival',''),json.dumps(r,ensure_ascii=False,default=str)))
  with self._connect() as con:
   con.executemany('''INSERT INTO quote_snapshots(observed_at,origin,destination,departure_date,return_date,price_twd,airline,source,mode,direct,outbound_departure,outbound_arrival,return_departure,return_arrival,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',entries)
  return len(entries)
 def save_insight(self,origin,destination,dep,ret,insight,retrieved_at=None):
  if not isinstance(insight,dict):return 0
  retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
  band=insight.get('typical_price_range') or []
  low,high=(band[0],band[1]) if len(band)>=2 else (None,None)
  level=insight.get('price_level')
  history=insight.get('price_history') or []
  entries=[]
  for sample in history:
   if not isinstance(sample,(list,tuple)) or len(sample)<2:continue
   try:
    when=datetime.fromtimestamp(float(sample[0]),timezone.utc).isoformat(timespec='seconds'); price=float(sample[1])
    if price<=0:continue
   except (ValueError,TypeError,OverflowError,OSError):continue
   entries.append((retrieved_at,origin,destination,dep,ret,level,low,high,when,price,'SerpApi Google Flights price_insights'))
  # Save the range/level even when the provider does not supply historical points.
  if not entries:entries=[(retrieved_at,origin,destination,dep,ret,level,low,high,None,None,'SerpApi Google Flights price_insights')]
  with self._connect() as con:
   con.executemany('''INSERT OR REPLACE INTO price_insights(retrieved_at,origin,destination,departure_date,return_date,price_level,typical_low_twd,typical_high_twd,history_time,history_price_twd,source) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',entries)
  return len(history)
 def quotes(self,origin=None,destination=None):
  q='SELECT observed_at,origin,destination,departure_date,return_date,price_twd,airline,source,mode,direct,outbound_departure,outbound_arrival,return_departure,return_arrival FROM quote_snapshots WHERE 1=1';args=[]
  if origin:q+=' AND origin=?';args.append(origin)
  if destination:q+=' AND destination=?';args.append(destination)
  q+=' ORDER BY observed_at ASC,id ASC'
  with self._connect() as con:
   con.row_factory=sqlite3.Row
   return [dict(row) for row in con.execute(q,args)]
 def insights(self,origin=None,destination=None):
  q='SELECT retrieved_at,origin,destination,departure_date,return_date,price_level,typical_low_twd,typical_high_twd,history_time,history_price_twd,source FROM price_insights WHERE 1=1';args=[]
  if origin:q+=' AND origin=?';args.append(origin)
  if destination:q+=' AND destination=?';args.append(destination)
  q+=' ORDER BY history_time ASC'
  with self._connect() as con:
   con.row_factory=sqlite3.Row
   return [dict(row) for row in con.execute(q,args)]

def analyze_trends(quotes,insights=None):
 """Per-itinerary minimum, recent value and simple interpretable buy-signal.
 Requires comparable same itinerary quote observations; source-mode differences remain visible.
 """
 groups={}; bands={}
 for r in quotes:
  if r['mode'] in ('TEST','LEGACY_UNDATED'):continue
  key=(r['departure_date'],r['return_date'])
  groups.setdefault(key,[]).append(r)
 for r in insights or []:
  key=(r['departure_date'],r['return_date'])
  if key not in bands or r['retrieved_at']>bands[key]['retrieved_at']:bands[key]=r
 out=[]
 for (dep,ret),rows in groups.items():
  rows.sort(key=lambda r:r['observed_at'])
  latest_time=rows[-1]['observed_at']
  current=[r for r in rows if r['observed_at']==latest_time]
  best_current=min(current,key=lambda r:r['price_twd'])
  # Per-snapshot lows, avoiding multiple options in one search masquerading as history.
  unique={}
  for r in rows:
   key=(r['observed_at'],r['source'],r['mode'])
   unique[key]=min(unique.get(key,float('inf')),r['price_twd'])
  same=[p for (ts,s,m),p in unique.items() if s==best_current['source'] and m==best_current['mode']]
  previous=[r['price_twd'] for r in rows if r['observed_at']<latest_time and r['source']==best_current['source'] and r['mode']==best_current['mode']]
  historic_min=min(same)
  typical=median(same)
  delta=round((best_current['price_twd']/typical-1)*100,1) if typical else None
  insight=bands.get((dep,ret)) or {}
  level=insight.get('price_level')
  lo=insight.get('typical_low_twd');hi=insight.get('typical_high_twd')
  if len(same)>=3:
   signal=('觀察低點' if best_current['price_twd']<=historic_min else '高於觀察低點')
  elif level in ('low','typical','high'):
   signal={'low':'平台顯示偏低','typical':'平台顯示一般','high':'平台顯示偏高'}[level]
  else:signal='樣本不足'
  out.append({'departure_date':dep,'return_date':ret,'latest_price_twd':best_current['price_twd'],
   'observed_min_twd':historic_min,'observed_median_twd':round(typical),
   'discount_vs_observed_median_pct':delta,'samples':len(same),
   'price_change_from_previous_twd':round(best_current['price_twd']-previous[-1]) if previous else None,
   'price_level':level,'typical_low_twd':lo,'typical_high_twd':hi,
   'signal':signal,'observed_at':latest_time,'source':best_current['source'],'mode':best_current['mode']})
 return sorted(out,key=lambda r:(r['latest_price_twd'],r['departure_date']))
