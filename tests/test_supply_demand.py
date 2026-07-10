import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.supply_demand_loader import fetch_or_load_supply_demand


class SupplyDemandTest(unittest.TestCase):
    def test_latest_margin_and_weekly_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "margin.csv"
            path.write_text(
                "code,as_of_date,long_margin_outstanding,short_margin_outstanding,source\n"
                "1234,2026-07-03,100,50,test\n1234,2026-07-10,80,40,test\n", encoding="utf-8"
            )
            result, missing = fetch_or_load_supply_demand("1234", date(2026, 7, 10), path)
            self.assertEqual(result["margin_ratio"], 2.0)
            self.assertAlmostEqual(result["long_weekly_change"], -0.2)
            self.assertEqual(missing, [])


if __name__ == "__main__": unittest.main()
