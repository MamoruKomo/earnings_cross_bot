import unittest

from src.evaluator import build_outcome, classify_outcome


RULES = {"outcome": {"win_return_threshold": 0.03, "lose_return_threshold": -0.03}}


class EvaluatorTest(unittest.TestCase):
    def test_classify_outcome_win_if_open_or_close_above_threshold(self):
        self.assertEqual(classify_outcome(0.031, -0.01, RULES), "win")
        self.assertEqual(classify_outcome(0.00, 0.04, RULES), "win")

    def test_classify_outcome_lose_only_if_open_and_close_below_threshold(self):
        self.assertEqual(classify_outcome(-0.031, -0.04, RULES), "lose")
        self.assertEqual(classify_outcome(-0.04, -0.01, RULES), "neutral")

    def test_build_outcome_returns_expected_fields(self):
        outcome = build_outcome(
            recommendation_id=1,
            code="1234",
            event_date="2026-07-09",
            evaluation_date="2026-07-10",
            event_price={"close": 100},
            next_price={"open": 104, "high": 106, "low": 99, "close": 103},
            rules=RULES,
        )
        self.assertEqual(outcome["result"], "win")
        self.assertEqual(round(outcome["next_open_return"], 4), 0.04)
        self.assertEqual(round(outcome["max_drawdown"], 4), -0.01)


if __name__ == "__main__":
    unittest.main()
