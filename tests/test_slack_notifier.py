import unittest
from unittest.mock import MagicMock, patch

from src.slack_notifier import format_recommendation_message, post_message


class SlackNotifierTest(unittest.TestCase):
    def test_formats_public_data_source(self):
        message = format_recommendation_message({"date": "2026-07-13", "data_sources": ["traders_web"], "recommendations": []})
        self.assertIn("データ元：トレーダーズ・ウェブ", message)

    def test_posts_json_to_webhook(self):
        response = MagicMock(); response.status = 200
        response.__enter__.return_value = response
        with patch("src.slack_notifier.request.urlopen", return_value=response) as urlopen:
            self.assertTrue(post_message("接続テスト", "https://hooks.slack.test/example"))
            request = urlopen.call_args.args[0]
            self.assertIn("接続テスト".encode("utf-8"), request.data)

    def test_formats_traders_web_announcement_time(self):
        message = format_recommendation_message({
            "date": "2026-08-04",
            "recommendations": [{
                "code": "4062", "name": "イビデン", "score": 74, "action": "cross",
                "announcement_time": "15:40", "announcement_time_source": "traders_web",
                "positive_factors": [], "risk_factors": [],
            }],
        })
        self.assertIn("決算発表時刻：15:40（Traders Web取得）", message)


if __name__ == "__main__": unittest.main()
