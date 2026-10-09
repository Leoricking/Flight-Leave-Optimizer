import unittest, tempfile
from pathlib import Path
from datetime import date,timedelta
from forecast import daily_lows,project_price
from automation import candidates,DEFAULT_CONFIG

class TestForecast(unittest.TestCase):
 def test_insufficient(self):
  out=project_price([(date(2026,10,1),9000)],'2026-11-01',today=date(2026,10,5))
  self.assertEqual(out['status'],'INSUFFICIENT')
 def test_ready(self):
  series=[(date(2026,10,1)+timedelta(days=i),11000-i*100) for i in range(10)]
  out=project_price(series,'2026-11-01',today=date(2026,10,10))
  self.assertEqual(out['status'],'EXPLORATORY')
  self.assertLess(out['scenario_price_twd'],out['latest_twd'])
  self.assertLess(out['scenario_low_twd'],out['scenario_high_twd'])
 def test_no_mix(self):
  q=[{'departure_date':'2026-11-01','return_date':'2026-11-05','mode':'SEARCH_RESULT','source':'A','observed_at':'2026-10-01T01:00:00+00:00','price_twd':9000},
     {'departure_date':'2026-11-01','return_date':'2026-11-05','mode':'INDICATIVE','source':'A','observed_at':'2026-10-01T02:00:00+00:00','price_twd':7000},
     {'departure_date':'2026-11-01','return_date':'2026-11-05','mode':'SEARCH_RESULT','source':'B','observed_at':'2026-10-01T03:00:00+00:00','price_twd':8000}]
  self.assertEqual(daily_lows(q,'2026-11-01','2026-11-05','A','SEARCH_RESULT'),[(date(2026,10,1),9000)])
 def test_dates(self):
  cfg={**DEFAULT_CONFIG,'earliest_departure':'2026-10-20','latest_return':'2026-11-16'}
  out=candidates(cfg,date(2026,10,9))
  self.assertTrue(any(x['departure_date']=='2026-10-31' and x['return_date']=='2026-11-04' and x['leave_days']==3 for x in out))
if __name__=='__main__':unittest.main()
