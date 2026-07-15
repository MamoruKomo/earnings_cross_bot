from __future__ import annotations

from typing import Any


def score_candidate(features: dict[str, Any], news: list[dict[str, Any]], themes: list[str], rules: dict[str, Any]) -> dict[str, Any]:
    weights = rules.get("weights", {})
    components = {
        "liquidity": _liquidity(features) * float(weights.get("liquidity", 20)),
        "volatility": _volatility(features) * float(weights.get("volatility", 15)),
        "news": _news(news) * float(weights.get("news", 20)),
        "theme": _theme(themes, news) * float(weights.get("theme", 10)),
        "technical": _technical(features) * float(weights.get("technical", 20)),
        "order_book": 0.35 * float(weights.get("order_book", 5)),
        "risk_reward": _risk_reward(features) * float(weights.get("risk_reward", 10)),
    }
    score = int(round(sum(components.values())))
    ranking = rules.get("ranking", {})
    excluded = []
    if (features.get("projected_turnover") or features.get("turnover") or 0) < float(ranking.get("minimum_turnover", 100_000_000)): excluded.append("売買代金不足")
    price = features.get("price")
    if price is None or not float(ranking.get("minimum_price", 100)) <= price <= float(ranking.get("maximum_price", 50_000)): excluded.append("価格帯対象外")
    if excluded: score = min(score, 49)
    return {"score": score, "components": {key: round(value, 2) for key, value in components.items()}, "excluded": excluded}


def select_ranked(rows: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    ranking = rules.get("ranking", {}); minimum = int(ranking.get("minimum_score", 55)); limit = int(ranking.get("max_candidates", 10))
    selected = [row for row in rows if row["score"] >= minimum and not row.get("excluded")]
    return sorted(selected, key=lambda row: (row["score"], row["code"]), reverse=True)[:limit]


def _liquidity(f: dict[str, Any]) -> float:
    turnover = float(f.get("projected_turnover") or f.get("turnover") or 0); volume_ratio = float(f.get("volume_ratio") or 0)
    return min(1.0, turnover / 2_000_000_000) * 0.65 + min(1.0, volume_ratio / 2.0) * 0.35


def _volatility(f: dict[str, Any]) -> float:
    atr = float(f.get("atr_rate") or 0); vol = float(f.get("volatility_20d") or 0)
    atr_score = max(0.0, 1 - abs(atr - 0.035) / 0.035); vol_score = max(0.0, 1 - abs(vol - 0.45) / 0.45)
    return atr_score * 0.7 + vol_score * 0.3


def _news(items: list[dict[str, Any]]) -> float:
    if not items: return 0.2
    score = sum(1 if item["sentiment"] == "positive" else -0.7 if item["sentiment"] == "negative" else 0.1 for item in items)
    return max(0.0, min(1.0, 0.45 + score * 0.25))


def _theme(themes: list[str], news: list[dict[str, Any]]) -> float:
    news_themes = {theme for item in news for theme in item.get("themes", [])}
    return min(1.0, 0.25 + len(set(themes) | news_themes) * 0.25)


def _technical(f: dict[str, Any]) -> float:
    signals = [f.get("above_vwap"), f.get("above_ma5"), f.get("above_ma20"), f.get("breakout_20d"), f.get("box_breakout")]
    base = sum(value is True for value in signals) / len(signals)
    rsi = f.get("rsi"); rsi_score = 0.8 if rsi is not None and 50 <= rsi <= 72 else 0.4
    gap = f.get("gap_rate"); gap_score = 0.8 if gap is not None and 0.005 <= gap <= 0.05 else 0.35
    return base * 0.6 + rsi_score * 0.2 + gap_score * 0.2


def _risk_reward(f: dict[str, Any]) -> float:
    atr = float(f.get("atr_rate") or 0); gap = abs(float(f.get("gap_rate") or 0))
    if not atr: return 0.25
    return max(0.0, min(1.0, (atr * 2.5 - gap) / 0.08 + 0.4))
