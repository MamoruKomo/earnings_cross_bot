from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any


def week_range(target_date: date) -> tuple[date, date]:
    start = target_date - timedelta(days=target_date.weekday())
    return start, target_date


def summarize_week(outcomes: list[dict[str, Any]], week_start: date, week_end: date) -> dict[str, Any]:
    if not outcomes:
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "recommendation_count": 0,
            "win": 0,
            "lose": 0,
            "neutral": 0,
            "avg_next_open_return": None,
            "avg_next_close_return": None,
            "best": None,
            "worst": None,
            "success_patterns": [],
            "failure_patterns": [],
            "rule_change_suggestions": ["推奨がない週はルール変更しない"],
        }

    rows = [dict(row) for row in outcomes]
    result_counts = {result: sum(1 for row in rows if row["result"] == result) for result in ("win", "lose", "neutral")}
    best = max(rows, key=lambda row: row.get("next_close_return") or 0)
    worst = min(rows, key=lambda row: row.get("next_close_return") or 0)
    avg_open = mean(row["next_open_return"] for row in rows if row.get("next_open_return") is not None)
    avg_close = mean(row["next_close_return"] for row in rows if row.get("next_close_return") is not None)
    suggestions = []
    if result_counts["lose"] > result_counts["win"]:
        suggestions.append("loseが多いため、20営業日リターン上限とリスク減点を強める案を検討")
    if avg_open < 0:
        suggestions.append("翌日始値平均がマイナスのため、寄り付き反応の過去データ重みを上げる案を検討")
    if not suggestions:
        suggestions.append("現行ルールを維持し、サンプルを増やしてから変更判断")
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "recommendation_count": len(rows),
        **result_counts,
        "avg_next_open_return": avg_open,
        "avg_next_close_return": avg_close,
        "best": {"code": best["code"], "next_close_return": best["next_close_return"]},
        "worst": {"code": worst["code"], "next_close_return": worst["next_close_return"]},
        "success_patterns": ["win銘柄の価格・財務特徴量を次回レビューで確認"],
        "failure_patterns": ["lose/neutral銘柄の過熱感と出尽くしリスクを確認"],
        "rule_change_suggestions": suggestions,
    }


def render_rules_suggestion(review: dict[str, Any]) -> str:
    lines = [
        "version: mvp-0.1",
        f"generated_at: {review.get('week_end')}",
        "source: weekly_review",
        "suggestions:",
    ]
    for suggestion in review.get("rule_change_suggestions", []):
        lines.append(f"  - {suggestion}")
    return "\n".join(lines) + "\n"

