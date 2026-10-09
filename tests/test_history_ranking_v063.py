import io
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from core import generate
from history import PriceHistory
from history_ranking import rank_rows, select_historical_offers
from report import excel_bytes


class HistoricalRankingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.db = PriceHistory(Path(self.tmp.name) / 'history.sqlite3')
        self.candidates = generate(date(2026, 10, 20), date(2026, 11, 16), 5, 3, {date(2026, 10, 26)})
        self.sample = {
            'departure_date': '2026-10-31', 'return_date': '2026-11-04',
            'price_twd': 8098, 'airline': 'Scoot', 'source': 'SerpApi / Google Flights',
            'mode': 'SEARCH_RESULT', 'direct': True,
            'outbound_arrival': '2026-10-31T11:00:00+09:00',
            'return_departure': '2026-11-04T18:00:00+09:00',
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_after_new_history_instance_no_api(self):
        self.db.save_offers('TPE','CTS',[self.sample], observed_at='2026-10-09T09:00:00+00:00')
        reloaded = PriceHistory(self.db.path)
        selected = select_historical_offers(self.candidates,reloaded.quotes('TPE','CTS'))
        ranked, summary = rank_rows(self.candidates,selected)
        self.assertEqual(ranked[0]['price_twd'],8098)
        self.assertEqual(ranked[0]['leave_days'],3)
        self.assertTrue(any(row['lowest_price_twd']==8098 for row in summary))
        self.assertTrue(any(row['lowest_price_twd'] is None for row in summary))

    def test_minimum_versus_latest_and_test_excluded(self):
        self.db.save_offers('TPE','CTS',[self.sample],observed_at='2026-10-09T09:00:00+00:00')
        self.db.save_offers('TPE','CTS',[dict(self.sample,price_twd=10000)],observed_at='2026-10-10T09:00:00+00:00')
        self.db.save_offers('TPE','CTS',[dict(self.sample,price_twd=100,mode='TEST')],observed_at='2026-10-11T09:00:00+00:00')
        quotes = self.db.quotes('TPE','CTS')
        self.assertEqual(select_historical_offers(self.candidates,quotes)[0]['price_twd'],8098)
        self.assertEqual(select_historical_offers(self.candidates,quotes,strategy='最近一次報價')[0]['price_twd'],10000)

    def test_direct_filter_and_excel_offline(self):
        self.db.save_offers('TPE','CTS',[self.sample],observed_at='2026-10-09T09:00:00+00:00')
        quotes = self.db.quotes('TPE','CTS')
        offers=select_historical_offers(self.candidates,quotes)
        ranked,summary=rank_rows(self.candidates,offers,direct_only=True)
        blob=excel_bytes([],[],quotes,historic_summary=summary,historic_ranked=ranked)
        import pandas as pd
        excel=pd.ExcelFile(io.BytesIO(blob))
        self.assertIn('歷史航班排名',excel.sheet_names)
        sheet=pd.read_excel(excel,sheet_name='歷史航班排名')
        self.assertEqual(len(sheet),1)
        self.assertIn('observed_at',sheet.columns)
        self.assertEqual(sheet.iloc[0]['price_twd'],8098)


if __name__ == '__main__':
    unittest.main()
