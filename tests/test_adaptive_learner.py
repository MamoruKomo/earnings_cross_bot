import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import db
from src.adaptive_learner import apply_learned_weights, train_profile, write_profile


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


if __name__ == "__main__": unittest.main()
