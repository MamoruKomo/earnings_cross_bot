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
        self.assertIsNone(data["latest_notification"])

    def test_dashboard_exposes_pending_decision_and_notification(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        db.insert_recommendation(
            conn, recommendation_date="2026-07-13", event_date="2026-07-13",
            rec={"code": "4443", "name": "Sansan", "score": 71, "action": "cross", "confidence": "medium",
                 "announcement_time": "15:00", "thesis": "Growth remains strong", "positive_factors": [],
                 "risk_factors": ["Crowded long"], "expected_reaction": "", "evaluation_rule": "",
                 "missing_data": ["supply_demand"]},
            score_details={}, model_version="test", rules_version="test",
            llm_output={"date": "2026-07-13", "recommendations": []},
        )
        db.record_notification(conn, "2026-07-13", "morning", "sent", {"candidate_count": 1, "data_status": "ok"})
        conn.commit()

        data = build_dashboard_data(conn)
        self.assertEqual(data["pending_recommendations"][0]["confidence"], "medium")
        self.assertEqual(data["pending_recommendations"][0]["risk_factors"], ["Crowded long"])
        self.assertEqual(data["latest_notification"]["status"], "sent")
        self.assertEqual(data["latest_notification"]["candidate_count"], 1)

    def test_decision_center_explains_selected_and_rejected_candidates(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        selected = {
            "code": "4062", "name": "イビデン", "score": 76, "action": "cross",
            "announcement_time": "15:40", "announcement_time_source": "traders_web",
            "missing_data": ["supply_demand"], "risk_flags": [],
            "price_features": {"chart_summary": "上昇基調", "return_20d": 0.08},
            "financial_features": {"operating_profit_yoy": 0.3, "revision_expectation_score": 90},
            "reaction_features": {}, "supply_demand_features": {},
            "sector_context": {"sector": "電気機器", "mood": "strong", "summary": "電気機器は追い風"},
            "components": {"earnings_growth": 18}, "context_adjustments": {"total": 3},
        }
        rejected = {
            "code": "9999", "name": "見送り", "score": 58, "action": "avoid",
            "announcement_time": "不明", "missing_data": ["announcement_time_unknown"],
            "risk_flags": ["announcement_time_unverified"], "price_features": {},
            "financial_features": {}, "reaction_features": {}, "supply_demand_features": {},
        }
        output = {"date": "2026-08-04", "market_note": "テスト", "no_trade_reason": "", "recommendations": [{
            "code": "4062", "name": "イビデン", "score": 76, "action": "cross", "announcement_time": "15:40",
            "thesis": "業績と地合いを評価", "positive_factors": ["増益"], "risk_factors": ["需給未取得"],
        }]}
        db.insert_llm_run(conn, "recommendation", "test", "prompt", {
            "date": "2026-08-04", "selected_candidates": [selected], "all_scored": [selected, rejected]
        }, output, "success")
        db.insert_recommendation(
            conn, "2026-08-04", "2026-08-04", output["recommendations"][0], selected, "test", "test", output
        )
        db.record_notification(conn, "2026-08-04", "morning", "sent", {"candidate_count": 1, "data_status": "ok"})
        conn.commit()

        center = build_dashboard_data(conn)["decision_center"]
        self.assertEqual("evaluation_overdue", center["state"])
        self.assertEqual("15:40", center["recommendations"][0]["announcement_time"])
        self.assertEqual("電気機器は追い風", center["recommendations"][0]["sector"]["summary"])
        self.assertEqual("9999", center["considered"][0]["code"])
        self.assertIn("announcement_time_unverified", center["considered"][0]["risk_factors"])


if __name__ == "__main__":
    unittest.main()
