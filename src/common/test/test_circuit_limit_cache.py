import tempfile
import unittest
from pathlib import Path

from circuit_limit_cache import CircuitLimitCache, clamp_limit_to_circuit


class TestClampLimit(unittest.TestCase):
    def test_buy_clamps_above_upper(self):
        # MON100-style band
        result = clamp_limit_to_circuit(327.37, "BUY", 327.09, 218.07, 1.0)
        self.assertEqual(result, 327.09)

    def test_sell_clamps_below_lower(self):
        result = clamp_limit_to_circuit(200.0, "SELL", 327.09, 218.07, 1.0)
        self.assertEqual(result, 218.07)

    def test_buy_unchanged_inside_band(self):
        result = clamp_limit_to_circuit(300.0, "BUY", 327.09, 218.07, 1.0)
        self.assertEqual(result, 300.0)


class TestCircuitLimitCache(unittest.TestCase):
    def test_lazy_load_and_clamp(self):
        csv_body = (
            '"security_id","symbol","exchange","upper_limit","lower_limit","tick_size"\n'
            '"22739","MON100","NSE","327.0900","218.0700","1.0000"\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            nse = Path(tmp) / "nse.csv"
            bse = Path(tmp) / "bse.csv"
            nse.write_text(csv_body, encoding="utf-8")
            bse.write_text('"security_id","symbol","exchange","upper_limit","lower_limit","tick_size"\n', encoding="utf-8")
            cache = CircuitLimitCache(nse_csv=nse, bse_csv=bse)
            db = {
                "SECURITY_ID": "22739",
                "MKT": "NSE",
                "MKT_SYMBOL": "MON100",
                "STRATEGY": "MANUAL",
                "REC_DATE": "20-May-2026",
                "REC_TIME": "10:00",
            }
            clamped = cache.clamp_for_open_order(db, 327.37, "BUY")
            self.assertEqual(clamped, 327.09)
            clamped2 = cache.clamp_for_open_order(db, 327.37, "BUY")
            self.assertEqual(clamped2, 327.09)


if __name__ == "__main__":
    unittest.main()
