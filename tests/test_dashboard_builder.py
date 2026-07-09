import sqlite3
import unittest

from src import db
from src.dashboard_builder import build_dashboard_data


class DashboardBuilderTest(unittest.TestCase):
    def test_build_dashboard_data_summarizes_accuracy(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        rec_id = db.insert_recommendation(
            conn,
            recommendation_date="2026-07-09",
            event_date="2026-07-09",
            rec={
                "code": "1234",
                "name": "Example",
                "score": 78,
                "action": "cross",
                "confidence": "medium",
                "announcement_time": "15:00",
                "thesis": "",
                "positive_factors": [],
                "risk_factors": [],
                "expected_reaction": "",
                "evaluation_rule": "",
                "missing_data": [],
            },
            score_details={},
            model_version="test",
            rules_version="test",
            llm_output={"date": "2026-07-09", "recommendations": []},
        )
        db.insert_outcome(
            conn,
            {
                "recommendation_id": rec_id,
                "code": "1234",
                "event_date": "2026-07-09",
                "evaluation_date": "2026-07-10",
                "event_close": 100.0,
                "next_open": 104.0,
                "next_high": 106.0,
                "next_low": 99.0,
                "next_close": 103.0,
                "next_open_return": 0.04,
                "next_high_return": 0.06,
                "next_low_return": -0.01,
                "next_close_return": 0.03,
                "max_drawdown": -0.01,
                "result": "win",
            },
        )
        conn.commit()

        data = build_dashboard_data(conn)
        self.assertEqual(data["summary"]["recommendation_count"], 1)
        self.assertEqual(data["summary"]["evaluated_count"], 1)
        self.assertEqual(data["summary"]["hit_rate"], 1.0)
        self.assertEqual(data["result_distribution"]["win"], 1)
        self.assertEqual(data["by_code"][0]["code"], "1234")
        self.assertEqual(data["summary"]["no_trade_day_count"], 0)


if __name__ == "__main__":
    unittest.main()
