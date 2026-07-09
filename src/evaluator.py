from __future__ import annotations

from typing import Any


def build_outcome(
    recommendation_id: int,
    code: str,
    event_date: str,
    evaluation_date: str,
    event_price: dict[str, Any],
    next_price: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    event_close = float(event_price["close"])
    next_open = float(next_price["open"])
    next_high = float(next_price["high"])
    next_low = float(next_price["low"])
    next_close = float(next_price["close"])
    next_open_return = pct_return(event_close, next_open)
    next_high_return = pct_return(event_close, next_high)
    next_low_return = pct_return(event_close, next_low)
    next_close_return = pct_return(event_close, next_close)
    return {
        "recommendation_id": recommendation_id,
        "code": code,
        "event_date": event_date,
        "evaluation_date": evaluation_date,
        "event_close": event_close,
        "next_open": next_open,
        "next_high": next_high,
        "next_low": next_low,
        "next_close": next_close,
        "next_open_return": next_open_return,
        "next_high_return": next_high_return,
        "next_low_return": next_low_return,
        "next_close_return": next_close_return,
        "max_drawdown": min(next_open_return, next_low_return, next_close_return),
        "result": classify_outcome(next_open_return, next_close_return, rules),
    }


def pct_return(base: float, value: float) -> float:
    if base == 0:
        return 0.0
    return (value / base) - 1.0


def classify_outcome(next_open_return: float, next_close_return: float, rules: dict[str, Any]) -> str:
    thresholds = rules.get("outcome", {})
    win_threshold = float(thresholds.get("win_return_threshold", 0.03))
    lose_threshold = float(thresholds.get("lose_return_threshold", -0.03))
    if next_open_return >= win_threshold or next_close_return >= win_threshold:
        return "win"
    if next_open_return <= lose_threshold and next_close_return <= lose_threshold:
        return "lose"
    return "neutral"

