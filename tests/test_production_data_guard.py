import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src import db
from src.calendar_loader import load_events_for_date
from src.dashboard_builder import build_dashboard_data
from src.financial_loader import fetch_or_load_financials
from src.price_loader import fetch_or_load_prices
from src.public_data_client import PublicDataError


class ProductionDataGuardTest(unittest.TestCase):
    def test_production_prices_never_fall_back_to_mock_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            path.write_text("date,code,open,high,low,close,volume,source\n2026-07-01,1234,1,2,1,2,100,mock\n", encoding="utf-8")
            with patch("src.price_loader.fetch_yahoo_prices", side_effect=PublicDataError("offline")):
                rows = fetch_or_load_prices("1234", date(2026, 7, 1), date(2026, 7, 2), path, allow_mock=False)
            self.assertEqual(rows, [])

    def test_production_financials_never_use_mock_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "financials.csv"
            path.write_text("code,revenue\n1234,999\n", encoding="utf-8")
            with patch("src.financial_loader.fetch_traders_financials", side_effect=PublicDataError("offline")):
                rows, source = fetch_or_load_financials("1234", date(2026, 7, 1), path, allow_mock=False)
            self.assertEqual(rows, [])
            self.assertEqual(source, "missing")

    def test_production_calendar_ignores_manual_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            path.write_text("date,code,name,announcement_time,source\n2026-07-01,1234,Dummy,15:30,mock\n", encoding="utf-8")
            with patch("src.calendar_loader.fetch_earnings_calendar", side_effect=PublicDataError("offline")):
                rows = load_events_for_date(path, date(2026, 7, 1), allow_manual=False)
            self.assertEqual(rows, [])

    def test_dashboard_excludes_existing_mock_recommendations(self):
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; db.init_db(conn)
        db.upsert_earnings_event(conn, {"date": "2026-07-01", "code": "1234", "name": "Dummy", "announcement_time": "15:30", "fiscal_quarter": "Q1", "source": "mock"})
        db.insert_recommendation(conn, "2026-07-01", "2026-07-01", {
            "code": "1234", "name": "Dummy", "score": 99, "action": "strong_cross", "confidence": "high",
            "announcement_time": "15:30", "thesis": "dummy", "positive_factors": [], "risk_factors": [],
            "expected_reaction": "", "evaluation_rule": "", "missing_data": [],
        }, {}, "test", "test", {})
        conn.commit()
        self.assertEqual(build_dashboard_data(conn)["summary"]["recommendation_count"], 0)


if __name__ == "__main__": unittest.main()
