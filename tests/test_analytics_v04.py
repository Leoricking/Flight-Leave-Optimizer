import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from history import PriceHistory
from analytics import observed_series, technical_indicators, price_stats

class PriceTests(unittest.TestCase):
    def test_history_saved_and_scoped(self):
        with TemporaryDirectory() as tmp:
            h=PriceHistory(Path(tmp)/'store.db')
            v={'departure_date':'2026-10-31','return_date':'2026-11-04','price_twd':8500,'source':'SerpApi','mode':'SEARCH_RESULT'}
            h.save_offers('TPE','CTS',[v], '2026-10-01T01:00:00+00:00')
            h.save_offers('TPE','CTS',[{**v,'price_twd':8000}], '2026-10-02T01:00:00+00:00')
            h.save_offers('TPE','CTS',[{**v,'mode':'TEST','price_twd':1}], '2026-10-03T01:00:00+00:00')
            s=observed_series(h.quotes('TPE','CTS'),'2026-10-31','2026-11-04','SerpApi','SEARCH_RESULT')
            self.assertEqual(len(s),2)
            self.assertEqual(price_stats(s)['observed_low_twd'],8000)
            self.assertTrue(technical_indicators(s)['rsi14'].isna().all())
    def test_daily_observation_not_market_ticks(self):
        entries=[dict(departure_date='2026-10-31',return_date='2026-11-04',mode='MANUAL',source='X',
                 observed_at='2026-10-01T00:00:00+00:00',price_twd=v) for v in [7000,7400]]
        s=observed_series(entries,'2026-10-31','2026-11-04','X','MANUAL')
        self.assertEqual(s.iloc[0]['close'],7000)
        self.assertEqual(s.iloc[0]['high'],7000)
