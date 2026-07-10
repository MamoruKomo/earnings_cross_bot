from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import load_config
from src.slack_notifier import post_message, webhook_configured


def main() -> None:
    load_config()
    stamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")
    message = f"【決算跨ぎAI 接続テスト】\n時刻：{stamp} JST\n状態：Slack Incoming Webhookは正常です"
    sent = post_message(message)
    print(f"[slack-test] configured={webhook_configured()} sent={sent}")


if __name__ == "__main__": main()
