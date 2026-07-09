from __future__ import annotations

import json
import os
from typing import Any
from urllib import request


def format_recommendation_message(payload: dict[str, Any]) -> str:
    lines = ["【本日の決算跨ぎ候補】", f"日付：{payload.get('date', '')}", ""]
    recommendations = payload.get("recommendations") or []
    if not recommendations:
        lines.append("本日は無理に跨ぐ銘柄なし")
        reason = payload.get("no_trade_reason")
        if reason:
            lines.extend(["", f"理由：{reason}"])
        return "\n".join(lines).strip()

    for index, rec in enumerate(recommendations, start=1):
        lines.extend(
            [
                f"{index}. {rec.get('name', '')}（{rec.get('code', '')}）",
                f"   スコア：{rec.get('score', '')}点",
                f"   判断：{rec.get('action', '')}",
                f"   発表予定：{rec.get('announcement_time', '')}",
                "",
                "理由：",
            ]
        )
        lines.extend([f"・{item}" for item in rec.get("positive_factors", [])])
        lines.extend(["", "リスク："])
        lines.extend([f"・{item}" for item in rec.get("risk_factors", [])])
        lines.extend(["", "検証：", rec.get("evaluation_rule", ""), ""])
    return "\n".join(lines).strip()


def post_message(message: str, webhook_url: str | None = None) -> bool:
    url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("[slack] SLACK_WEBHOOK_URL is not set. Message preview:")
        print(message)
        return False
    payload = json.dumps({"text": message}, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=20) as response:
            if response.status >= 400:
                print(f"[slack] post failed: HTTP {response.status}")
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"[slack] post failed: {exc}")
        return False

