import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.daytrade.features import build_features
from src.daytrade.evaluator import _post_selection_bars
from src.daytrade.news import analyze_news
from src.daytrade.notifier import format_ranking
from src.daytrade.reasoner import build_comment
from src.daytrade.scoring import score_candidate, select_ranked
from src.daytrade.storage import connect, recent_dashboard, save_outcome, save_run


class DaytradeTest(unittest.TestCase):
    def setUp(self):
        self.daily = []
        for index in range(35):
            close = 1000 + index * 4
            self.daily.append({"date": f"2026-05-{index + 1:02d}", "open": close - 5, "high": close + 15, "low": close - 15, "close": close, "volume": 1_000_000})
        self.intraday = [
            {"datetime": "2026-07-15T00:00:00+00:00", "open": 1160, "high": 1180, "low": 1155, "close": 1175, "volume": 300_000},
            {"datetime": "2026-07-15T00:05:00+00:00", "open": 1175, "high": 1190, "low": 1170, "close": 1185, "volume": 350_000},
        ]

    def test_features_include_vwap_atr_and_volume_projection(self):
        result = build_features({"daily": self.daily, "intraday": self.intraday, "quote_meta": {}})
        self.assertIsNotNone(result["vwap"])
        self.assertGreater(result["atr"], 0)
        self.assertGreater(result["projected_turnover"], result["turnover"])
        self.assertIn("order_book", result["unavailable"])

    def test_news_sentiment_and_theme(self):
        result = analyze_news({"title": "生成AI事業で大型受注、上方修正", "code": "1234"}, {"AI": ["生成AI"]})
        self.assertEqual(result["sentiment"], "positive")
        self.assertEqual(result["themes"], ["AI"])

    def test_scoring_and_selection(self):
        features = build_features({"daily": self.daily, "intraday": self.intraday, "quote_meta": {}})
        rules = {"weights": {"liquidity": 20, "volatility": 15, "news": 20, "theme": 10, "technical": 20, "order_book": 5, "risk_reward": 10}, "ranking": {"minimum_turnover": 1, "minimum_price": 100, "maximum_price": 50000, "minimum_score": 1, "max_candidates": 10}}
        score = score_candidate(features, [{"sentiment": "positive", "themes": ["AI"]}], ["AI"], rules)
        self.assertGreater(score["score"], 0)
        self.assertEqual(len(select_ranked([{"code": "1234", **score}], rules)), 1)

    def test_stop_is_below_price_when_vwap_is_above_price(self):
        comment = build_comment({"features": {"price": 1000, "atr": 30, "vwap": 1020, "above_vwap": False, "unavailable": []}, "news": []})
        self.assertLess(comment["stop_loss"], 1000)

    def test_evaluation_uses_only_bars_after_selection(self):
        rows = [
            {"datetime": "2026-07-15T00:05:00+00:00", "close": 100},
            {"datetime": "2026-07-15T00:10:00+00:00", "close": 101},
        ]
        result = _post_selection_bars(rows, date(2026, 7, 15), "2026-07-15T00:05:00+00:00")
        self.assertEqual([row["close"] for row in result], [101])

    def test_storage_round_trip_and_message(self):
        features = {"price": 1000, "gap_rate": 0.02, "volume_ratio": 2.0}
        candidate = {"rank": 1, "code": "1234", "name": "Example", "score": 80, "themes": ["AI"], "features": features, "components": {}, "news": [], "comment": {"reasons": ["出来高急増"], "entry_strategy": "VWAP押し目", "take_profit": 1030, "stop_loss": 980, "risks": ["板確認"]}}
        with tempfile.TemporaryDirectory() as directory:
            conn = connect(Path(directory) / "daytrade.db")
            save_run(conn, "2026-07-15", 8, [candidate], {"date": "2026-07-15"})
            row = conn.execute("SELECT * FROM daytrade_candidates").fetchone()
            save_outcome(conn, row, {"reference_price": 1000, "high": 1040, "low": 990, "close": 1020, "max_up": 0.04, "max_down": -0.01, "close_return": 0.02, "target_hit": True, "stop_hit": False, "analysis": {}})
            conn.commit()
            self.assertEqual(recent_dashboard(conn)["summary"]["hit_rate"], 1.0)
        message = format_ranking({"date": "2026-07-15", "candidates": [candidate]})
        self.assertIn("デイトレ銘柄ランキング", message)
        self.assertIn("利確候補", message)


if __name__ == "__main__": unittest.main()
