"""Date generation, local travel estimates, offer scoring; stdlib only."""
from __future__ import annotations
import csv
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path

HOLIDAYS_2026 = {date(2026, 10, 26): '光復節補假'}  # 其他年份請自行提供 holiday CSV


def holiday_set(path: str = 'data/holidays.csv') -> set[date]:
    result = set(HOLIDAYS_2026)
    p = Path(path)
    if p.exists():
        with p.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('date'):
                    result.add(date.fromisoformat(row['date']))
    return result


def working_days(start: date, end: date, holidays: set[date]) -> list[date]:
    return [start + timedelta(days=i) for i in range((end-start).days+1)
            if (start + timedelta(days=i)).weekday() < 5 and (start + timedelta(days=i)) not in holidays]


def generate(start: date, end: date, trip_days: int, max_leave: int, holidays: set[date]) -> list[dict]:
    if trip_days < 2 or end < start: return []
    dates = []
    for i in range((end - start).days + 1):
        dep = start + timedelta(days=i)
        ret = dep + timedelta(days=trip_days-1)
        if ret > end: break
        leave = working_days(dep,ret,holidays)
        if len(leave) <= max_leave:
            dates.append({'departure_date':dep.isoformat(),'return_date':ret.isoformat(),
                          'leave_days':len(leave),'leave_dates':','.join(d.isoformat() for d in leave)})
    return dates


def _time(value):
    if not value: return None
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def local_hours(arrival: str, departure: str, arrival_buffer_hours=2.0, airport_buffer_hours=3.0):
    """Arrival in CTS, departure from CTS. Timestamp offsets must be included; naive times interpreted as local."""
    a, b = _time(arrival), _time(departure)
    if not a or not b: return None
    if (a.tzinfo is None) != (b.tzinfo is None): return None
    h = (b-a).total_seconds()/3600 - arrival_buffer_hours - airport_buffer_hours
    return max(0, round(h,1))


def score(row: dict, transport_twd: int = 1200, overnight_twd: int = 0, luggage_twd: int = 0, min_usable_hours: float = 0):
    row = dict(row)
    row['total_cost_twd'] = round(float(row['price_twd']) + transport_twd + overnight_twd + luggage_twd)
    hours = local_hours(row.get('outbound_arrival',''),row.get('return_departure',''))
    row['usable_hours'] = hours
    row['cost_per_hour'] = round(row['total_cost_twd']/hours,2) if hours and hours >= min_usable_hours else None
    return row


def manual_csv(path):
    with open(path, encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            dep = row.get('departure_date','').strip(); ret = row.get('return_date','').strip()
            if not dep or not ret: continue
            try: price = float(row.get('price_twd',''))
            except ValueError: continue
            if price <= 0: continue
            row['price_twd'] = price
            row['source'] = row.get('source') or 'MANUAL'
            row['direct'] = str(row.get('direct','')).strip().lower() in ('true','1','yes','y','是')
            row['mode'] = 'MANUAL'
            yield row


def join_offers(dates, offers, transport_twd=1200, overnight_twd=0, luggage_twd=0, direct_only=False):
    eligible = {(d['departure_date'],d['return_date']):d for d in dates}
    results=[]
    for offer in offers:
        key = offer.get('departure_date'),offer.get('return_date')
        if key not in eligible: continue
        if direct_only and not offer.get('direct',False): continue
        try: r=score({**eligible[key],**offer},transport_twd,overnight_twd,luggage_twd)
        except (TypeError,ValueError):continue
        results.append(r)
    return sorted(results,key=lambda r:(r['total_cost_twd'], -(r['usable_hours'] or 0)))
