from __future__ import annotations

from math import sqrt
from statistics import mean, stdev
from typing import Any


def compute_price_features(prices: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    rows = [row for row in prices if row.get("close") not in (None, "")]
    rows = sorted(rows, key=lambda row: row["date"])
    missing: list[str] = []
    if len(rows) < 20:
        missing.append("price_history_20d")
    if len(rows) < 60:
        missing.append("price_history_60d")

    closes = [float(row["close"]) for row in rows]
    volumes = [float(row.get("volume") or 0) for row in rows]
    turnovers = [float(row.get("turnover_value") or (float(row["close"]) * float(row.get("volume") or 0))) for row in rows]

    returns = [_pct(closes[i], closes[i - 1]) for i in range(1, len(closes))]
    recent_20_returns = returns[-20:]
    recent_high = max(closes[-60:] if len(closes) >= 60 else closes) if closes else None
    latest_close = closes[-1] if closes else None

    features = {
        "latest_close": latest_close,
        "return_5d": _window_return(closes, 5),
        "return_20d": _window_return(closes, 20),
        "return_60d": _window_return(closes, 60),
        "avg_volume_20d": mean(volumes[-20:]) if len(volumes) >= 20 else None,
        "avg_turnover_20d": mean(turnovers[-20:]) if len(turnovers) >= 20 else None,
        "volatility_20d": stdev(recent_20_returns) * sqrt(20) if len(recent_20_returns) >= 2 else None,
        "pre_earnings_overheat": _window_return(closes, 20),
        "distance_from_recent_high": _pct(latest_close, recent_high) if latest_close and recent_high else None,
        "price_rows": len(rows),
    }
    for key, value in features.items():
        if value is None and key not in {"return_60d"}:
            missing.append(key)
    return features, sorted(set(missing))


def compute_financial_features(statements: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    if not statements:
        return ({}, ["financial_statement"])
    latest = sorted(statements, key=lambda row: row.get("disclosed_date") or "")[-1]
    revenue_progress = _progress(latest.get("cumulative_revenue") or latest.get("revenue"), latest.get("full_year_revenue_forecast"))
    op_progress = _progress(
        latest.get("cumulative_operating_profit") or latest.get("operating_profit"),
        latest.get("full_year_operating_profit_forecast"),
    )
    revision_score = _revision_expectation_score(
        latest.get("revenue_yoy"),
        latest.get("operating_profit_yoy"),
        revenue_progress,
        op_progress,
        latest.get("operating_margin_change"),
    )
    features = {
        "disclosed_date": latest.get("disclosed_date"),
        "fiscal_quarter": latest.get("fiscal_quarter"),
        "revenue": latest.get("revenue"),
        "operating_profit": latest.get("operating_profit"),
        "ordinary_profit": latest.get("ordinary_profit"),
        "net_income": latest.get("net_income"),
        "operating_margin": latest.get("operating_margin"),
        "revenue_yoy": latest.get("revenue_yoy"),
        "operating_profit_yoy": latest.get("operating_profit_yoy"),
        "operating_margin_change": latest.get("operating_margin_change"),
        "revenue_progress_rate": revenue_progress,
        "operating_profit_progress_rate": op_progress,
        "revision_expectation_score": revision_score,
        "theme_score": latest.get("theme_score"),
        "risk_notes": latest.get("risk_notes") or "",
    }
    required = [
        "revenue_yoy",
        "operating_profit_yoy",
        "operating_margin_change",
        "revenue_progress_rate",
        "operating_profit_progress_rate",
    ]
    missing = [key for key in required if features.get(key) is None]
    if features["risk_notes"]:
        features["risk_flags"] = [item.strip() for item in features["risk_notes"].split(";") if item.strip()]
    else:
        features["risk_flags"] = []
    return features, missing


def _window_return(values: list[float], window: int) -> float | None:
    if len(values) <= window or values[-window - 1] == 0:
        return None
    return _pct(values[-1], values[-window - 1])


def _pct(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value in (None, 0):
        return None
    return (new_value / old_value) - 1


def _progress(actual: Any, forecast: Any) -> float | None:
    if actual in (None, "") or forecast in (None, "", 0):
        return None
    return float(actual) / float(forecast)


def _revision_expectation_score(
    revenue_yoy: Any,
    op_yoy: Any,
    revenue_progress: float | None,
    op_progress: float | None,
    margin_change: Any,
) -> float:
    values = [
        _normalize_growth(revenue_yoy),
        _normalize_growth(op_yoy),
        _normalize_progress(revenue_progress),
        _normalize_progress(op_progress),
        _normalize_growth(margin_change),
    ]
    usable = [value for value in values if value is not None]
    return round(mean(usable) * 100, 2) if usable else 0.0


def _normalize_growth(value: Any) -> float | None:
    if value in (None, ""):
        return None
    value = float(value)
    return max(0.0, min(1.0, (value + 0.10) / 0.40))


def _normalize_progress(value: Any) -> float | None:
    if value in (None, ""):
        return None
    value = float(value)
    return max(0.0, min(1.0, (value - 0.20) / 0.25))

