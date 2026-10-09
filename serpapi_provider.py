"""SerpApi Google Flights: roundtrip indicative prices and optional verified paired legs."""
from datetime import datetime
import requests

URL = 'https://serpapi.com/search.json'

def _query(params, key, timeout=90):
    r=requests.get(URL,params={**params,'api_key':key,'engine':'google_flights','hl':'zh-TW','currency':'TWD'},timeout=timeout)
    r.raise_for_status()
    data=r.json()
    if data.get('error'): raise RuntimeError(str(data['error']))
    return data

def _read_leg(flights):
    if not flights: return ('','','',False)
    first,last=flights[0],flights[-1]
    return (first.get('departure_airport',{}).get('time',''),last.get('arrival_airport',{}).get('time',''),
            ','.join(dict.fromkeys(str(x.get('airline','')) for x in flights)),len(flights)==1)

def serpapi_search(origin,destination,dep,ret,key,confirm_return=False,max_pairings=1,insights_sink=None):
    """Initial result: round-trip headline price with outbound details; second stage picks specific return.

    Initial results have mode=INDICATIVE and are NOT guaranteed complete roundtrip itineraries.
    """
    params={'departure_id':origin,'arrival_id':destination,'outbound_date':dep,
            'return_date':ret,'type':1,'adults':1,'travel_class':1}
    data=_query(params,key)
    if insights_sink is not None:
        insights_sink.append({'departure_date':dep,'return_date':ret,'price_insights':data.get('price_insights') or {}})
    checked=datetime.now().astimezone().isoformat(timespec='seconds')
    items=(data.get('best_flights') or [])+(data.get('other_flights') or [])
    rows=[]
    pairs=[]
    for item in items:
        price=item.get('price')
        if not isinstance(price,(int,float)) or price<=0:continue
        o_dep,o_arr,airline,direct=_read_leg(item.get('flights') or [])
        row={'departure_date':dep,'return_date':ret,'price_twd':price,'airline':airline,
             'direct':False,'outbound_direct':direct,'return_direct':None,
             'outbound_departure':o_dep,'outbound_arrival':o_arr,
             'return_departure':'','return_arrival':'','source':'SerpApi / Google Flights',
             'mode':'INDICATIVE','checked_at':checked,'booking_url':'https://www.google.com/travel/flights',
             'note':'來回搜尋顯示的參考總價；尚未選定回程，不能確認完整航班與直飛'}
        rows.append(row)
        pairs.append((item,row))
    if not confirm_return:return rows
    confirmed=[]
    for item,row in pairs:
        token=item.get('departure_token')
        if not token or len(confirmed)>=max_pairings:continue
        return_results=_query({**params,'departure_token':token},key)
        return_items=(return_results.get('best_flights') or [])+(return_results.get('other_flights') or [])
        for ret_item in return_items:
            price=ret_item.get('price')
            if not isinstance(price,(int,float)) or price<=0:continue
            r_dep,r_arr,r_airline,r_direct=_read_leg(ret_item.get('flights') or [])
            confirmed.append({**row,'price_twd':price,'direct':bool(row['outbound_direct'] and r_direct),
                              'return_direct':r_direct,'return_departure':r_dep,'return_arrival':r_arr,
                              'airline':', '.join(filter(None,[row['airline'],r_airline])),
                              'mode':'SEARCH_RESULT','note':'已選定去程及回程搜尋結果，仍須至供應商驗證價格及可售性'})
            break
    return confirmed or rows
