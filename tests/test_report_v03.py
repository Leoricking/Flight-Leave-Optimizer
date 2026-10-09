import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from report import make_summary,add_ranks,excel_bytes,csv_bytes,COLUMNS,SUMMARY_COLUMNS

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.dates=[{'departure_date':'2026-10-24','return_date':'2026-10-28','leave_days':2,'leave_dates':'2026-10-27,2026-10-28'},
                    {'departure_date':'2026-10-31','return_date':'2026-11-04','leave_days':3,'leave_dates':'2026-11-02,2026-11-03,2026-11-04'},
                    {'departure_date':'2026-11-01','return_date':'2026-11-05','leave_days':4,'leave_dates':'2026-11-02,2026-11-03,2026-11-04,2026-11-05'}]
        self.offers=[dict(self.dates[1],price_twd=8098,total_cost_twd=9298,usable_hours=85.9,mode='SEARCH_RESULT',airline='酷航',source='SerpApi',direct=True),
                     dict(self.dates[1],price_twd=8899,total_cost_twd=10099,usable_hours=91,mode='SEARCH_RESULT',airline='航司',source='SerpApi',direct=True)]
    def test_date_rows_no_missing_dates(self):
        s=make_summary(self.dates,add_ranks(self.offers))
        self.assertEqual(len(s),3)
        self.assertEqual(s[1]['lowest_price_twd'],8098)
        self.assertEqual(s[2]['price_status'],'未取得')
        self.assertIsNone(s[2]['lowest_price_twd'])
    def test_excel_valid_sheets(self):
        from zipfile import ZipFile
        b=excel_bytes(make_summary(self.dates,add_ranks(self.offers)),add_ranks(self.offers))
        with ZipFile(io.BytesIO(b)) as z:
            wb=z.read('xl/workbook.xml').decode()
            self.assertIn('所有日期最低票價',wb)
            self.assertIn('航班排名',wb)
            self.assertIn('報表說明',wb)
    def test_csv_utf8_bom(self):
        out=csv_bytes(make_summary(self.dates,self.offers),SUMMARY_COLUMNS)
        self.assertTrue(out.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(out.decode('utf-8-sig').count('2026-10-31'),1)
if __name__=='__main__':unittest.main()
