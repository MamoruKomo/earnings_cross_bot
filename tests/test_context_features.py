import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.feature_engineering import compute_financial_features, compute_price_features
from src.market_context import load_sector_context
from src.scorer import score_candidate


class ContextFeatureTests(unittest.TestCase):
    def test_chart_detects_uptrend(self):
        prices = [{"date": f"2026-01-{i:02d}", "close": 100 + i, "volume": 1000 + i} for i in range(1, 29)]
        features, _ = compute_price_features(prices)
        self.assertEqual("strong_uptrend", features["chart_trend"])
        self.assertIn("上昇基調", features["chart_summary"])

    def test_previous_financial_comparison(self):
        rows = [
            {"disclosed_date": "2026-01-01", "operating_profit_yoy": 0.10, "operating_margin": 0.08},
            {"disclosed_date": "2026-04-01", "operating_profit_yoy": 0.30, "operating_margin": 0.12},
        ]
        features, _ = compute_financial_features(rows)
        self.assertEqual("improving", features["previous_comparison"]["direction"])

    def test_sector_context_uses_morning_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "market_intelligence/docs/data"
            data.mkdir(parents=True)
            (data / "fundamentals.json").write_text(json.dumps({"items": [{"code": "1234", "sector": "機械"}]}))
            (data / "briefs.json").write_text(json.dumps({"briefs": [{
                "date": "2026-08-04", "summary_bullets": ["日経平均(2026-08-04): 1 (-1.10%)"],
                "sector_leaders": [{"name": "機械", "return": 0.02}], "sector_laggards": []
            }]}))
            context, missing = load_sector_context(root, "1234", date(2026, 8, 4))
            self.assertEqual("strong", context["mood"])
            self.assertAlmostEqual(-0.011, context["market_return"])
            self.assertEqual([], missing)

    def test_context_adjustments_change_score(self):
        rules = {"scoring_weights": {}, "thresholds": {}}
        base = score_candidate({"code": "1"}, {}, {}, {}, {}, [], rules, {"mood": "neutral"})
        stronger = score_candidate(
            {"code": "1"}, {"chart_trend": "strong_uptrend"},
            {"previous_comparison": {"direction": "improving"}}, {"previous_close_return": 0.04}, {}, [], rules,
            {"mood": "strong", "market_return": 0.02},
        )
        self.assertGreater(stronger["score"], base["score"])


if __name__ == "__main__":
    unittest.main()
