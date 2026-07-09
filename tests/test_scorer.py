import unittest

from src.scorer import classify_score, score_candidate, select_recommendations


def rules():
    return {
        "thresholds": {
            "min_average_turnover": 50_000_000,
            "min_average_volume": 50_000,
            "overheat_20d_return": 0.25,
            "exclude_20d_return": 0.45,
            "max_missing_fields_before_avoid": 6,
        },
        "scoring_weights": {
            "earnings_growth": 20,
            "progress_revision": 20,
            "low_overheat": 15,
            "historical_reaction": 15,
            "liquidity": 10,
            "theme": 10,
            "low_risk": 10,
        },
        "recommendation": {"minimum_post_score": 70, "max_recommendations": 3},
    }


class ScorerTest(unittest.TestCase):
    def test_classify_score_thresholds(self):
        self.assertEqual(classify_score(80), "strong_cross")
        self.assertEqual(classify_score(70), "cross")
        self.assertEqual(classify_score(60), "watch")
        self.assertEqual(classify_score(59), "avoid")

    def test_score_candidate_selects_high_quality_name(self):
        scored = score_candidate(
            event={"code": "1234", "name": "Example", "announcement_time": "15:00"},
            price_features={
                "return_20d": 0.04,
                "distance_from_recent_high": -0.05,
                "avg_turnover_20d": 200_000_000,
                "avg_volume_20d": 300_000,
            },
            financial_features={
                "revenue_yoy": 0.18,
                "operating_profit_yoy": 0.30,
                "operating_margin_change": 0.03,
                "revision_expectation_score": 82,
                "theme_score": 8,
                "risk_flags": [],
            },
            reaction_features={
                "positive_reaction_ratio": 0.75,
                "avg_next_close_return": 0.025,
            },
            missing_data=[],
            rules=rules(),
        )
        self.assertGreaterEqual(scored["score"], 70)
        self.assertIn(scored["action"], {"cross", "strong_cross"})
        self.assertEqual(select_recommendations([scored], rules())[0]["code"], "1234")

    def test_low_liquidity_forces_avoid_zone(self):
        scored = score_candidate(
            event={"code": "9999", "name": "Thin", "announcement_time": "15:00"},
            price_features={
                "return_20d": 0.02,
                "distance_from_recent_high": -0.04,
                "avg_turnover_20d": 1_000_000,
                "avg_volume_20d": 5_000,
            },
            financial_features={
                "revenue_yoy": 0.50,
                "operating_profit_yoy": 0.50,
                "operating_margin_change": 0.05,
                "revision_expectation_score": 95,
                "theme_score": 10,
                "risk_flags": [],
            },
            reaction_features={
                "positive_reaction_ratio": 1.0,
                "avg_next_close_return": 0.05,
            },
            missing_data=[],
            rules=rules(),
        )
        self.assertLessEqual(scored["score"], 59)
        self.assertIn("low_liquidity", scored["risk_flags"])


if __name__ == "__main__":
    unittest.main()
