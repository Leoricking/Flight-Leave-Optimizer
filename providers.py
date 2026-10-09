"""Duffel offer-request API provider. No scraping, no invented price data."""
import os
import requests
from datetime import datetime

API = 'https://api.duffel.com/air/offer_requests'


def duffel_search(origin: str, destination: str, dep: str, ret: str, token: str, currency='TWD', timeout=45):
    if not token: raise ValueError('請設定 DUFFEL_ACCESS_TOKEN')
    headers = {'Authorization':f'Bearer {token}','Duffel-Version':'v2','Accept':'application/json','Content-Type':'application/json'}
    payload = {'data': {'slices':[{'origin':origin,'destination':destination,'departure_date':dep},
                                   {'origin':destination,'destination':origin,'departure_date':ret}],
                        'passengers':[{'type':'adult'}], 'cabin_class':'economy'}}
    resp=requests.post(API,headers=headers,params={'return_offers':'true','supplier_timeout':25000},json=payload,timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f'Duffel HTTP {resp.status_code}: {resp.text[:400]}')
    data=resp.json().get('data') or {}
    offers=[]
    for offer in data.get('offers') or []:
        slices=offer.get('slices') or []
        if len(slices)!=2: continue
        try:
            outbound=slices[0]['segments']; inbound=slices[1]['segments']
            if not outbound or not inbound: continue
            price=float(offer['total_amount']); offer_currency=offer.get('total_currency')
            if offer_currency != 'TWD':
                # Do not silently compare different currencies as TWD.
                continue
            offers.append({'departure_date':dep,'return_date':ret,'price_twd':price,
                           'source':'Duffel','mode':'TEST' if token.startswith('duffel_test_') else 'LIVE',
                           'airline':','.join(sorted({s.get('operating_carrier',{}).get('name','') for x in slices for s in x.get('segments',[])})),
                           'direct':len(outbound)==1 and len(inbound)==1,
                           'outbound_departure':outbound[0].get('departing_at',''),
                           'outbound_arrival':outbound[-1].get('arriving_at',''),
                           'return_departure':inbound[0].get('departing_at',''),
                           'return_arrival':inbound[-1].get('arriving_at',''),
                           'offer_id':offer.get('id',''),
                           'expires_at':offer.get('expires_at',''),
                           'checked_at':datetime.now().astimezone().isoformat(timespec='seconds')})
        except (KeyError,ValueError,TypeError): continue
    return offers
