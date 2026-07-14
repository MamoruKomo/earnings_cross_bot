from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from statistics import mean
from typing import Any


def build_validation_report(conn: sqlite3.Connection, rules: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in conn.execute(
        """
        SELECT r.recommendation_date, r.code, r.score, r.action, r.model_version,
               o.next_open_return, o.next_close_return, o.max_drawdown, o.result
        FROM recommendations r JOIN outcomes o ON o.recommendation_id = r.id
        WHERE o.next_close_return IS NOT NULL
        ORDER BY o.evaluation_date, r.code
        """
    ).fetchall()]
    validation_size = int(rules.get("learning", {}).get("validation_samples", 10))
    minimum_train = int(rules.get("learning", {}).get("minimum_samples", 30))
    split = max(0, len(rows) - validation_size)
    train, holdout = rows[:split], rows[split:] if split >= minimum_train else []
    return {
        "status": "ready" if holdout else "collecting",
        "sample_count": len(rows),
        "training_count": len(train) if holdout else min(len(rows), minimum_train),
        "holdout_count": len(holdout),
        "required_count": minimum_train + validation_size,
        "all": metrics(rows),
        "holdout": metrics(holdout),
        "score_bands": score_bands(rows),
        "message": "直近データを学習から隔離して検証中" if holdout else f"時系列検証開始まであと{max(0, minimum_train + validation_size - len(rows))}件",
    }


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    wins = sum(1 for row in rows if row.get("result") == "win")
    returns = [float(row["next_close_return"]) for row in rows if row.get("next_close_return") is not None]
    lower, upper = wilson_interval(wins, count)
    return {
        "count": count,
        "correct": wins,
        "precision": wins / count if count else None,
        "precision_lower_95": lower,
        "precision_upper_95": upper,
        "avg_next_close_return": mean(returns) if returns else None,
        "positive_rate": sum(value > 0 for value in returns) / len(returns) if returns else None,
    }


def score_bands(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        score = int(row.get("score") or 0)
        grouped["80-100" if score >= 80 else "75-79" if score >= 75 else "70-74"].append(row)
    order = ("80-100", "75-79", "70-74")
    return [{"band": band, **metrics(grouped[band])} for band in order if grouped[band]]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)
