from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


def train_profile(conn: sqlite3.Connection, rules: dict[str, Any]) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT r.score_details_json, o.next_close_return
        FROM recommendations r JOIN outcomes o ON o.recommendation_id = r.id
        WHERE o.next_close_return IS NOT NULL ORDER BY o.evaluation_date, r.code
    """).fetchall()
    minimum = int(rules.get("learning", {}).get("minimum_samples", 30))
    profile: dict[str, Any] = {
        "version": 1, "trained_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sample_count": len(rows), "minimum_samples": minimum, "status": "observing",
        "weight_multipliers": {}, "feature_evidence": {},
    }
    if len(rows) < minimum:
        profile["message"] = f"学習開始まであと{minimum - len(rows)}件"
        return profile

    samples = []
    for row in rows:
        details = json.loads(row["score_details_json"] or "{}")
        samples.append((details.get("components") or {}, float(row["next_close_return"])))
    max_change = float(rules.get("learning", {}).get("maximum_weight_change", 0.10))
    for feature in rules.get("scoring_weights", {}):
        pairs = [(float(parts[feature]), result) for parts, result in samples if parts.get(feature) is not None]
        if len(pairs) < minimum: continue
        midpoint = mean(value for value, _ in pairs)
        high = [result for value, result in pairs if value >= midpoint]
        low = [result for value, result in pairs if value < midpoint]
        if not high or not low: continue
        edge = mean(high) - mean(low)
        multiplier = 1.0 + max(-max_change, min(max_change, edge * 2.0))
        profile["weight_multipliers"][feature] = round(multiplier, 4)
        profile["feature_evidence"][feature] = {"high_return": mean(high), "low_return": mean(low), "edge": edge}
    profile["status"] = "active"
    profile["message"] = "検証結果に基づく重み補正を適用"
    return profile


def apply_learned_weights(rules: dict[str, Any], path: Path) -> dict[str, float]:
    base = {key: float(value) for key, value in rules.get("scoring_weights", {}).items()}
    if not rules.get("learning", {}).get("enabled", False) or not path.exists(): return base
    try: profile = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError): return base
    if profile.get("status") != "active": return base
    adjusted = {key: value * float(profile.get("weight_multipliers", {}).get(key, 1.0)) for key, value in base.items()}
    total = sum(adjusted.values()) or 100.0
    return {key: value * 100.0 / total for key, value in adjusted.items()}


def write_profile(profile: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
