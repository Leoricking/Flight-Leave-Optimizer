import io,sys,unittest
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import generate,holiday_set,manual_csv,join_offers
from serpapi_provider import _read_leg
class NewTests(unittest.TestCase):
    def test_three_days_includes_nov(self):
        rows=generate(date(2026,10,20),date(2026,11,16),5,3,holiday_set(str(Path(__file__).resolve().parents[1]/'data/holidays.csv')))
        m=[r for r in rows if r['departure_date']=='2026-10-31']
        self.assertEqual(m[0]['leave_dates'],'2026-11-02,2026-11-03,2026-11-04')
    def test_two_days_excludes_nov(self):
        rows=generate(date(2026,10,20),date(2026,11,16),5,2,holiday_set())
        self.assertFalse(any(r['departure_date']=='2026-10-31' for r in rows))
    def test_manual_stream(self):
        content='departure_date,return_date,price_twd,direct\n2026-10-31,2026-11-04,9000,true\n'
        result=list(manual_csv(io.StringIO(content)))
        self.assertEqual(result[0]['price_twd'],9000)
    def test_leg(self):
        dep,arr,air,direct=_read_leg([{'departure_airport':{'time':'2026-10-31 06:00'},'arrival_airport':{'time':'2026-10-31 11:00'},'airline':'Airline A'}])
        self.assertTrue(direct)
        self.assertEqual(dep,'2026-10-31 06:00')
if __name__=='__main__':unittest.main()
