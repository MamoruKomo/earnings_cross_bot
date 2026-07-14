from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def train_profile(conn: sqlite3.Connection, rules: dict[str, Any]) -> dict[str, Any]:
    rows = conn.execute("""
        SELECT r.score_details_json, o.next_close_return
        FROM recommendations r JOIN outcomes o ON o.recommendation_id = r.id
        WHERE o.next_close_return IS NOT NULL ORDER BY o.evaluation_date, r.code
    """).fetchall()
    learning_rules = rules.get("learning", {})
    minimum = int(learning_rules.get("minimum_samples", 30))
    validation_size = int(learning_rules.get("validation_samples", 10))
    required = minimum + validation_size
    profile: dict[str, Any] = {
        "version": 1, "trained_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sample_count": len(rows), "minimum_samples": minimum, "validation_samples": validation_size,
        "required_samples": required, "status": "observing",
        "weight_multipliers": {}, "feature_evidence": {},
    }
    if len(rows) < required:
        profile["message"] = f"時系列検証開始まであと{required - len(rows)}件"
        return profile

    training_rows = rows[:-validation_size]
    holdout_rows = rows[-validation_size:]
    samples = []
    for row in training_rows:
        details = json.loads(row["score_details_json"] or "{}")
        samples.append((details.get("components") or {}, float(row["next_close_return"])))
    max_change = float(learning_rules.get("maximum_weight_change", 0.10))
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
    validation = validate_multipliers(holdout_rows, profile["weight_multipliers"], rules)
    profile["validation"] = validation
    if learning_rules.get("require_holdout_improvement", True) and not validation["passed"]:
        profile["status"] = "rejected"
        profile["weight_multipliers"] = {}
        profile["message"] = "直近ホールドアウトで改善せず、重み変更を見送り"
    else:
        profile["status"] = "active"
        profile["message"] = "直近ホールドアウトで改善を確認し、重み補正を適用"
    return profile


def validate_multipliers(rows: list[sqlite3.Row], multipliers: dict[str, float], rules: dict[str, Any]) -> dict[str, Any]:
    threshold = int(rules.get("recommendation", {}).get("minimum_post_score", 70))
    base_results = [float(row["next_close_return"]) for row in rows]
    adjusted_results = []
    for row in rows:
        details = json.loads(row["score_details_json"] or "{}")
        components = details.get("components") or {}
        adjusted_score = sum(float(value) * float(multipliers.get(key, 1.0)) for key, value in components.items())
        if adjusted_score >= threshold:
            adjusted_results.append(float(row["next_close_return"]))
    base_precision = sum(value >= 0.03 for value in base_results) / len(base_results) if base_results else 0.0
    adjusted_precision = sum(value >= 0.03 for value in adjusted_results) / len(adjusted_results) if adjusted_results else 0.0
    base_return = mean(base_results) if base_results else 0.0
    adjusted_return = mean(adjusted_results) if adjusted_results else 0.0
    minimum_coverage = max(3, len(rows) // 2)
    passed = len(adjusted_results) >= minimum_coverage and adjusted_precision >= base_precision and adjusted_return >= base_return
    return {
        "holdout_count": len(rows), "selected_count": len(adjusted_results),
        "base_precision": base_precision, "adjusted_precision": adjusted_precision,
        "base_avg_return": base_return, "adjusted_avg_return": adjusted_return,
        "passed": passed,
    }


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
