"""Offline ranking of previously observed quotes. No network calls.

Historical lowest is not a currently purchasable price. Prefer comparing
consistent offer sources/modes, and expose observed_at for auditability.
"""
from __future__ import annotations
from datetime import datetime, timezone
from core import join_offers
from report import add_ranks, make_summary


def _parse_time(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def select_historical_offers(candidates, quotes, *, strategy='歷史最低價', include_test=False):
    """One quote per eligible travel-date pair, with source/time metadata.

    Historical lows: minimum price from stored snapshots.
    Latest: latest timestamp, then lowest price at that timestamp.
    Quotes with no valid observation timestamp are excluded from latest mode.
    """
    keys = {(d['departure_date'], d['return_date']) for d in candidates}
    groups = {}
    for quote in quotes:
        key = (quote.get('departure_date'), quote.get('return_date'))
        if key not in keys:
            continue
        if not include_test and str(quote.get('mode', '')).upper() == 'TEST':
            continue
        try:
            price = float(quote.get('price_twd'))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        if strategy == '最近一次報價' and not _parse_time(quote.get('observed_at')):
            continue
        groups.setdefault(key, []).append(dict(quote, price_twd=price))

    output = []
    for key, rows in groups.items():
        if strategy == '最近一次報價':
            latest = max(_parse_time(r['observed_at']) for r in rows)
            rows = [r for r in rows if _parse_time(r['observed_at']) == latest]
        best = min(rows, key=lambda r: (r['price_twd'], str(r.get('observed_at', ''))))
        best = dict(best)
        best['historical_status'] = '歷史報價，須重新核價'
        best['observed_at'] = str(best.get('observed_at') or '')
        output.append(best)
    return sorted(output, key=lambda r: (r['price_twd'], r['departure_date']))


def rank_rows(candidates, offers, transport=1200, overnight=0, luggage=0,
              direct_only=False, ranking='最低票價'):
    rows = join_offers(candidates, offers, transport, overnight, luggage, direct_only)
    if ranking == '最低票價':
        rows.sort(key=lambda r: (r['price_twd'], -(r.get('usable_hours') or 0)))
    elif ranking == '每小時旅遊成本最低':
        rows.sort(key=lambda r: (r.get('cost_per_hour') is None,
                                 r.get('cost_per_hour') if r.get('cost_per_hour') is not None else float('inf'),
                                 r['total_cost_twd']))
    elif ranking == '可玩時間最長':
        rows.sort(key=lambda r: (r.get('usable_hours') is None,
                                 -(r.get('usable_hours') or 0), r['total_cost_twd']))
    else:
        rows.sort(key=lambda r: (r['total_cost_twd'], -(r.get('usable_hours') or 0)))
    ranked = add_ranks(rows)
    return ranked, make_summary(candidates, ranked)
