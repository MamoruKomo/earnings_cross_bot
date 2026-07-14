import unittest

from src.validator import metrics, score_bands, wilson_interval


class ValidatorTest(unittest.TestCase):
    def test_metrics_reports_precision_and_uncertainty(self):
        rows = [
            {"result": "win", "next_close_return": 0.05},
            {"result": "neutral", "next_close_return": 0.01},
            {"result": "lose", "next_close_return": -0.04},
            {"result": "win", "next_close_return": 0.03},
        ]
        result = metrics(rows)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["correct"], 2)
        self.assertLess(result["precision_lower_95"], result["precision"])
        self.assertGreater(result["precision_upper_95"], result["precision"])

    def test_score_bands_do_not_mix_thresholds(self):
        rows = [
            {"score": 82, "result": "win", "next_close_return": 0.04},
            {"score": 77, "result": "neutral", "next_close_return": 0.01},
            {"score": 71, "result": "lose", "next_close_return": -0.05},
        ]
        self.assertEqual([row["band"] for row in score_bands(rows)], ["80-100", "75-79", "70-74"])

    def test_empty_wilson_interval_is_unknown(self):
        self.assertEqual(wilson_interval(0, 0), (None, None))


if __name__ == "__main__":
    unittest.main()
