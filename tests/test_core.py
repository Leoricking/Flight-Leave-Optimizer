import sys,unittest
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import generate,holiday_set,local_hours,join_offers
class CoreTests(unittest.TestCase):
    def test_holiday(self):
        dates=generate(date(2026,10,23),date(2026,10,27),5,2,holiday_set())
        self.assertEqual(len(dates),1)
        self.assertEqual(dates[0]['leave_dates'],'2026-10-23,2026-10-27')
    def test_oct_24(self):
        ds=generate(date(2026,10,24),date(2026,10,28),5,2,holiday_set())
        self.assertEqual(ds[0]['leave_days'],2)
    def test_hours(self):
        self.assertEqual(local_hours('2026-10-24T17:00:00+09:00','2026-10-28T18:00:00+09:00'),92.0)
    def test_price_filter(self):
        ds=generate(date(2026,10,24),date(2026,10,28),5,2,holiday_set())
        offers=[{'departure_date':'2026-10-24','return_date':'2026-10-28','price_twd':10000,'direct':True,'source':'MANUAL'}]
        self.assertEqual(join_offers(ds,offers,transport_twd=1200)[0]['total_cost_twd'],11200)
        self.assertEqual(len(join_offers(ds,offers,direct_only=True)),1)
    def test_unmatched_date(self):
        self.assertEqual(join_offers([], [{'departure_date':'2026-10-24','return_date':'2026-10-28','price_twd':10000}]),[])
if __name__=='__main__':unittest.main()
