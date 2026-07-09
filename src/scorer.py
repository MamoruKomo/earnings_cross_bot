from __future__ import annotations

from typing import Any


def score_candidate(
    event: dict[str, Any],
    price_features: dict[str, Any],
    financial_features: dict[str, Any],
    reaction_features: dict[str, Any],
    missing_data: list[str],
    rules: dict[str, Any],
) -> dict[str, Any]:
    weights = rules.get("scoring_weights", {})
    thresholds = rules.get("thresholds", {})
    missing = sorted(set(missing_data))
    risk_flags = list(financial_features.get("risk_flags") or [])

    components = {
        "earnings_growth": _earnings_growth(financial_features, weights.get("earnings_growth", 20)),
        "progress_revision": _progress_revision(financial_features, weights.get("progress_revision", 20)),
        "low_overheat": _low_overheat(price_features, weights.get("low_overheat", 15), thresholds),
        "historical_reaction": _historical_reaction(reaction_features, weights.get("historical_reaction", 15)),
        "liquidity": _liquidity(price_features, weights.get("liquidity", 10), thresholds),
        "theme": _theme(financial_features, weights.get("theme", 10)),
        "low_risk": _low_risk(missing, risk_flags, event, weights.get("low_risk", 10), thresholds),
    }

    total = int(round(sum(components.values())))
    exclude_reasons = exclusion_reasons(price_features, financial_features, missing, thresholds)
    if exclude_reasons:
        risk_flags.extend(exclude_reasons)
        total = min(total, 59)

    action = classify_score(total)
    return {
        "code": event["code"],
        "name": event.get("name", ""),
        "announcement_time": event.get("announcement_time", ""),
        "score": total,
        "action": action,
        "components": {key: round(value, 2) for key, value in components.items()},
        "missing_data": missing,
        "risk_flags": sorted(set(risk_flags)),
        "price_features": price_features,
        "financial_features": financial_features,
        "reaction_features": reaction_features,
    }


def classify_score(score: int) -> str:
    if score >= 80:
        return "strong_cross"
    if score >= 70:
        return "cross"
    if score >= 60:
        return "watch"
    return "avoid"


def select_recommendations(scored: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    rec_rules = rules.get("recommendation", {})
    minimum = int(rec_rules.get("minimum_post_score", 70))
    max_count = int(rec_rules.get("max_recommendations", 3))
    candidates = [row for row in scored if row.get("score", 0) >= minimum and row.get("action") in {"cross", "strong_cross"}]
    return sorted(candidates, key=lambda row: (row["score"], row["code"]), reverse=True)[:max_count]


def exclusion_reasons(
    price_features: dict[str, Any],
    financial_features: dict[str, Any],
    missing_data: list[str],
    thresholds: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    avg_turnover = price_features.get("avg_turnover_20d")
    if avg_turnover is not None and avg_turnover < thresholds.get("min_average_turnover", 50_000_000):
        reasons.append("low_liquidity")
    return_20d = price_features.get("return_20d")
    if return_20d is not None and return_20d > thresholds.get("exclude_20d_return", 0.45):
        reasons.append("too_much_pre_earnings_runup")
    if len(missing_data) > thresholds.get("max_missing_fields_before_avoid", 6):
        reasons.append("too_much_missing_data")
    if financial_features.get("operating_profit") is not None and financial_features["operating_profit"] < 0:
        reasons.append("operating_loss")
    return reasons


def _earnings_growth(financial: dict[str, Any], weight: float) -> float:
    values = [
        _growth_score(financial.get("revenue_yoy")),
        _growth_score(financial.get("operating_profit_yoy")),
        _growth_score(financial.get("operating_margin_change")),
    ]
    usable = [value for value in values if value is not None]
    if not usable:
        return weight * 0.2
    return weight * (sum(usable) / len(usable))


def _progress_revision(financial: dict[str, Any], weight: float) -> float:
    revision = financial.get("revision_expectation_score")
    if revision is not None:
        return weight * max(0.0, min(1.0, float(revision) / 100.0))
    values = [
        _progress_score(financial.get("revenue_progress_rate")),
        _progress_score(financial.get("operating_profit_progress_rate")),
    ]
    usable = [value for value in values if value is not None]
    return weight * (sum(usable) / len(usable)) if usable else weight * 0.2


def _low_overheat(price: dict[str, Any], weight: float, thresholds: dict[str, Any]) -> float:
    return_20d = price.get("return_20d")
    distance = price.get("distance_from_recent_high")
    if return_20d is None:
        return weight * 0.35
    overheat = thresholds.get("overheat_20d_return", 0.25)
    runup_score = 1.0 - max(0.0, min(1.0, return_20d / overheat))
    if return_20d < -0.10:
        runup_score *= 0.8
    distance_score = 0.8
    if distance is not None:
        distance_score = 1.0 if -0.12 <= distance <= -0.01 else 0.7 if distance < 0 else 0.45
    return weight * ((runup_score * 0.65) + (distance_score * 0.35))


def _historical_reaction(reaction: dict[str, Any], weight: float) -> float:
    ratio = reaction.get("positive_reaction_ratio")
    avg_close = reaction.get("avg_next_close_return")
    if ratio is None:
        return weight * 0.35
    ratio_score = max(0.0, min(1.0, float(ratio)))
    close_score = 0.5 if avg_close is None else max(0.0, min(1.0, (float(avg_close) + 0.03) / 0.08))
    return weight * ((ratio_score * 0.65) + (close_score * 0.35))


def _liquidity(price: dict[str, Any], weight: float, thresholds: dict[str, Any]) -> float:
    turnover = price.get("avg_turnover_20d")
    volume = price.get("avg_volume_20d")
    min_turnover = thresholds.get("min_average_turnover", 50_000_000)
    min_volume = thresholds.get("min_average_volume", 50_000)
    if turnover is None or volume is None:
        return weight * 0.35
    turnover_score = max(0.0, min(1.0, turnover / (min_turnover * 4)))
    volume_score = max(0.0, min(1.0, volume / (min_volume * 4)))
    return weight * ((turnover_score * 0.7) + (volume_score * 0.3))


def _theme(financial: dict[str, Any], weight: float) -> float:
    value = financial.get("theme_score")
    if value is None:
        return weight * 0.5
    return weight * max(0.0, min(1.0, float(value) / 10.0))


def _low_risk(
    missing_data: list[str],
    risk_flags: list[str],
    event: dict[str, Any],
    weight: float,
    thresholds: dict[str, Any],
) -> float:
    score = 1.0
    score -= min(0.45, len(missing_data) * 0.07)
    score -= min(0.35, len(risk_flags) * 0.12)
    if (event.get("announcement_time") or "").strip() in {"", "不明"}:
        score -= 0.15
    return weight * max(0.0, min(1.0, score))


def _growth_score(value: Any) -> float | None:
    if value in (None, ""):
        return None
    value = float(value)
    return max(0.0, min(1.0, (value + 0.10) / 0.35))


def _progress_score(value: Any) -> float | None:
    if value in (None, ""):
        return None
    value = float(value)
    return max(0.0, min(1.0, (value - 0.18) / 0.30))

