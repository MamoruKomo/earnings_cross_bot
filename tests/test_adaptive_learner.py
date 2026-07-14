import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import db
from src.adaptive_learner import apply_learned_weights, train_profile, validate_multipliers, write_profile


class AdaptiveLearnerTest(unittest.TestCase):
    def test_observes_until_minimum_sample_count(self):
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; db.init_db(conn)
        profile = train_profile(conn, {"learning": {"minimum_samples": 30}, "scoring_weights": {"growth": 100}})
        self.assertEqual(profile["status"], "observing")
        self.assertEqual(profile["sample_count"], 0)

    def test_inactive_profile_does_not_change_weights(self):
        rules = {"learning": {"enabled": True}, "scoring_weights": {"a": 60, "b": 40}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            write_profile({"status": "observing", "weight_multipliers": {"a": 1.1}}, path)
            self.assertEqual(apply_learned_weights(rules, path), {"a": 60.0, "b": 40.0})

    def test_holdout_rejects_adjustment_that_drops_all_candidates(self):
        rows = [
            {"score_details_json": '{"components":{"growth":70}}', "next_close_return": 0.04},
            {"score_details_json": '{"components":{"growth":70}}', "next_close_return": -0.01},
            {"score_details_json": '{"components":{"growth":70}}', "next_close_return": 0.05},
        ]
        result = validate_multipliers(rows, {"growth": 0.9}, {"recommendation": {"minimum_post_score": 70}})
        self.assertFalse(result["passed"])
        self.assertEqual(result["selected_count"], 0)


if __name__ == "__main__": unittest.main()
