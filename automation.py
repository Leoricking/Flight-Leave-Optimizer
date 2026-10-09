"""Headless scheduled quote capture; no Streamlit imports or GUI requirements."""
from __future__ import annotations
import argparse
from datetime import datetime, date, timedelta, timezone
import json, os, sys, time
from pathlib import Path
from core import generate, holiday_set
from history import PriceHistory
from serpapi_provider import serpapi_search

BASE=Path(__file__).resolve().parent
CONFIG_PATH=BASE/'data'/'monitor_config.json'

DEFAULT_CONFIG={
 'origin':'TPE','destination':'CTS','earliest_departure':'2026-10-20',
 'latest_return':'2026-11-16','trip_days':5,'max_leave':3,
 'min_leave':2,'max_searches_per_run':8,'confirm_return':False,
 'pause_seconds':2,'api_key_env':'SERPAPI_API_KEY',
 'max_days_before_departure':120,'alerts_below_twd':9500,
 'alert_drop_percent':8,'daily_run_limit':20
}

def load_config(path=CONFIG_PATH):
 p=Path(path)
 if not p.exists():
  p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text(json.dumps(DEFAULT_CONFIG,ensure_ascii=False,indent=2),encoding='utf-8')
 return {**DEFAULT_CONFIG,**json.loads(p.read_text(encoding='utf-8'))}

def candidates(config,today=None):
 today=today or date.today()
 start=max(date.fromisoformat(config['earliest_departure']),today)
 end=date.fromisoformat(config['latest_return'])
 if end<start:return []
 matches=generate(start,end,int(config['trip_days']),int(config['max_leave']),holiday_set(str(BASE/'data'/'holidays.csv')))
 return [c for c in matches if int(config.get('min_leave',0))<=c['leave_days']<=int(config['max_leave']) and (date.fromisoformat(c['departure_date'])-today).days<=int(config['max_days_before_departure'])]

def get_key(config):
 key=os.environ.get(config.get('api_key_env','SERPAPI_API_KEY'),'').strip()
 if not key:
  # Optional locally stored key, kept outside git.
  secret=BASE/'data'/'serpapi_key.txt'
  if secret.exists():key=secret.read_text(encoding='utf-8').strip()
 return key

def run(config=None,*,today=None,search=serpapi_search,sleep=time.sleep,db=None):
 config=config or load_config();today=today or date.today()
 key=get_key(config)
 if not key:raise RuntimeError('缺少 SERPAPI_API_KEY：請設定環境變數，或放在 data/serpapi_key.txt。')
 db=db or PriceHistory(BASE/'data'/'price_history.sqlite3')
 selection=candidates(config,today)
 statefile=BASE/'data'/'monitor_state.json'; statefile.parent.mkdir(parents=True,exist_ok=True)
 try: state=json.loads(statefile.read_text(encoding='utf-8'))
 except (FileNotFoundError,ValueError):state={}
 day=today.isoformat()
 if state.get('date')!=day:state={'date':day,'count':0,'rotation':0}
 daily_remaining=max(0,int(config['daily_run_limit'])-int(state['count']))
 limit=min(int(config['max_searches_per_run']),daily_remaining,len(selection))
 offset=int(state.get('rotation',0))%len(selection) if selection else 0
 ordered=selection[offset:]+selection[:offset]
 selected=ordered[:limit]
 result={'checked_at':datetime.now(timezone.utc).isoformat(),'total_candidates':len(selection),'attempted':0,'saved':0,'errors':[],'lowest_prices':[],'alerts':[],'dry_run':False}
 for index,pair in enumerate(selected):
  # Record attempt BEFORE network call, ensuring restarts cannot silently exceed the daily budget.
  state['count']+=1;state['rotation']=offset+index+1
  statefile.write_text(json.dumps(state,indent=2),encoding='utf-8')
  result['attempted']+=1
  try:
   insight=[]
   offers=search(config['origin'],config['destination'],pair['departure_date'],pair['return_date'],key,
      confirm_return=bool(config['confirm_return']),max_pairings=1,insights_sink=insight)
   previous=[x for x in db.quotes(config['origin'],config['destination']) if x['departure_date']==pair['departure_date'] and x['return_date']==pair['return_date'] and x['mode'] not in ('TEST',)]
   result['saved']+=db.save_offers(config['origin'],config['destination'],offers)
   for item in insight:db.save_insight(config['origin'],config['destination'],item['departure_date'],item['return_date'],item['price_insights'])
   real=[x for x in offers if x.get('mode')!='TEST' and x.get('price_twd')]
   if real:
    cheapest=min(real,key=lambda x:float(x['price_twd']))
    price=float(cheapest['price_twd'])
    result['lowest_prices'].append({'departure_date':pair['departure_date'],'return_date':pair['return_date'],'price_twd':price,'mode':cheapest.get('mode')})
    compatible=[float(x['price_twd']) for x in previous if x['source']==cheapest.get('source') and x['mode']==cheapest.get('mode')]
    if price<=float(config['alerts_below_twd']):result['alerts'].append(f"低於門檻 {pair['departure_date']}~{pair['return_date']}: TWD {price:,.0f} ({cheapest.get('mode')})")
    elif compatible and price<=min(compatible)*(1-float(config['alert_drop_percent'])/100):result['alerts'].append(f"低於歷史觀察最低 {pair['departure_date']}~{pair['return_date']}: TWD {price:,.0f}")
  except Exception as exc:
   result['errors'].append(f"{pair['departure_date']}~{pair['return_date']}: {exc}")
  if index<len(selected)-1:sleep(float(config['pause_seconds']))
 logfile=BASE/'data'/'monitor_log.jsonl'
 with logfile.open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
 if result['alerts']:
  (BASE/'data'/'latest_alerts.txt').write_text('\n'.join(result['alerts']),encoding='utf-8')
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',default=str(CONFIG_PATH));ap.add_argument('--dry-run',action='store_true');args=ap.parse_args()
 try:
  cfg=load_config(args.config)
  if args.dry_run:
   output={'candidates':candidates(cfg),'estimated_api_requests_max':min(int(cfg['max_searches_per_run']),len(candidates(cfg)))*(2 if cfg['confirm_return'] else 1)}
  else:output=run(cfg)
  print(json.dumps(output,ensure_ascii=False,indent=2,default=str));return 0 if not output.get('errors') else 2
 except Exception as exc:
  print(f'ERROR: {exc}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
