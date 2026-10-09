"""Conservative interpretable *scenario* estimates, not guaranteed future airfare quotes.

Use only matching itinerary/source/mode; observations on distinct days count as samples.
Forecast uses recent short-term drift with clipping and empirical volatility, and
refuses to estimate on insufficient longitudinal history.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, timezone
from statistics import median
import math

def daily_lows(quotes,dep,ret,source=None,mode=None):
 grouped=defaultdict(list)
 for q in quotes:
  if q.get('departure_date')!=dep or q.get('return_date')!=ret:continue
  if q.get('mode') in ('TEST','INDICATIVE','UNKNOWN','LEGACY_UNDATED'):continue
  if source is not None and q.get('source')!=source:continue
  if mode is not None and q.get('mode')!=mode:continue
  try:
   dt=datetime.fromisoformat(q['observed_at'].replace('Z','+00:00')).date()
   price=float(q['price_twd'])
   if price>0:grouped[dt].append(price)
  except (ValueError,TypeError,KeyError):continue
 return sorted((d,min(prices)) for d,prices in grouped.items())

def project_price(series,departure_date,lookahead_days=7,today=None):
 """Scenario: per-day robust drift, capped 2%/day; wide uncertainty band.
 Not a trained predictive model, uses no external market-wide airfare history.
 """
 today=today or date.today();departure=date.fromisoformat(departure_date)
 remaining=(departure-today).days
 if not series:return {'status':'NO_DATA','observations':0,'reason':'無已確認來回行程的歷史價格'}
 latest=series[-1][1];n=len(series)
 if remaining<=0:return {'status':'EXPIRED','observations':n,'latest_twd':round(latest),'reason':'出發日已到或已過'}
 if n<7 or (series[-1][0]-series[0][0]).days<7:
  return {'status':'INSUFFICIENT','observations':n,'latest_twd':round(latest),'reason':'至少需 7 個不同觀察日且橫跨 7 天，才能提供探索性情境推估'}
 daily_change=[]
 for (day_a,a),(day_b,b) in zip(series,series[1:]):
  span=(day_b-day_a).days
  if span>0:daily_change.append(math.log(b/a)/span)
 drift=max(-0.02,min(0.02,median(daily_change[-14:])))
 horizon=max(1,min(int(lookahead_days),remaining,14))
 future=latest*math.exp(drift*horizon)
 spread=median([abs(x-drift) for x in daily_change]) if daily_change else 0
 spread=max(0.035,min(0.30,(spread*1.4826)*math.sqrt(horizon)+0.035))
 low=max(0,future*(1-spread));high=future*(1+spread)
 observed_min=min(p for _,p in series)
 if latest<=observed_min*1.03:advice='目前接近自身觀察低價：優先核實是否可購，避免等待而失去座位。'
 elif drift<0:advice='近期觀察價有下降傾向，但不保證持續；可設定降價門檻追蹤。'
 else:advice='未觀察到明確持續下跌；若行程固定，建議以可負擔價格決策。'
 return {'status':'EXPLORATORY','observations':n,'span_days':(series[-1][0]-series[0][0]).days,
         'latest_twd':round(latest),'observed_low_twd':round(observed_min),'forecast_days':horizon,
         'scenario_price_twd':round(future),'scenario_low_twd':round(low),'scenario_high_twd':round(high),
         'median_daily_drift_pct':round((math.exp(drift)-1)*100,2),'confidence':'低（未校準模型）','advice':advice,
         'reason':'同日期、同來源、同類型歷史快照之穩健趨勢外推；非可售最低價預測'}
