from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def train(conn: sqlite3.Connection, rules: dict[str, Any]) -> dict[str, Any]:
    rows = list(conn.execute("""SELECT c.components_json, o.target_hit, o.close_return FROM daytrade_candidates c
      JOIN daytrade_outcomes o ON o.candidate_id=c.id ORDER BY o.trade_date, c.rank""").fetchall())
    cfg = rules.get("learning", {}); minimum = int(cfg.get("minimum_samples", 30)); validation_size = int(cfg.get("validation_samples", 10)); required = minimum + validation_size
    profile: dict[str, Any] = {"version": 1, "trained_at": _now(), "sample_count": len(rows), "required_samples": required, "status": "observing", "weight_multipliers": {}}
    if len(rows) < required:
        profile["message"] = f"時系列検証開始まであと{required - len(rows)}件"; return profile
    training, holdout = rows[:-validation_size], rows[-validation_size:]; max_change = float(cfg.get("maximum_weight_change", 0.10)); multipliers = {}
    for feature in rules.get("weights", {}):
        pairs = [(json.loads(row["components_json"]).get(feature), bool(row["target_hit"])) for row in training]
        pairs = [(float(value), hit) for value, hit in pairs if value is not None]
        if len(pairs) < minimum: continue
        midpoint = mean(value for value, _ in pairs); high = [hit for value, hit in pairs if value >= midpoint]; low = [hit for value, hit in pairs if value < midpoint]
        if not high or not low: continue
        edge = mean(high) - mean(low); multipliers[feature] = round(1 + max(-max_change, min(max_change, edge * 0.5)), 4)
    validation = _validate(holdout, multipliers, rules); profile["validation"] = validation
    if validation["passed"]:
        profile.update({"status": "active", "weight_multipliers": multipliers, "message": "未見データで精度悪化がないため補正を採用"})
    else:
        profile.update({"status": "rejected", "message": "未見データで改善せず補正を見送り"})
    return profile


def adjusted_rules(rules: dict[str, Any], profile_path: Path) -> dict[str, Any]:
    try: profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return rules
    if profile.get("status") != "active": return rules
    output = dict(rules); base = rules.get("weights", {}); multipliers = profile.get("weight_multipliers", {}); raw = {key: float(value) * float(multipliers.get(key, 1)) for key, value in base.items()}; total = sum(raw.values()) or 100
    output["weights"] = {key: value * 100 / total for key, value in raw.items()}; return output


def write_profile(conn: sqlite3.Connection, profile: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    conn.execute("INSERT INTO daytrade_learning_runs VALUES (NULL,?,?,?,?)", (profile["trained_at"], profile["sample_count"], profile["status"], json.dumps(profile, ensure_ascii=False, sort_keys=True))); conn.commit()


def _validate(rows: list[sqlite3.Row], multipliers: dict[str, float], rules: dict[str, Any]) -> dict[str, Any]:
    minimum_score = float(rules.get("ranking", {}).get("minimum_score", 55)); base_hits = [bool(row["target_hit"]) for row in rows]; selected = []
    for row in rows:
        components = json.loads(row["components_json"]); score = sum(float(value) * float(multipliers.get(key, 1)) for key, value in components.items())
        if score >= minimum_score: selected.append(bool(row["target_hit"]))
    base_precision = mean(base_hits) if base_hits else 0; adjusted_precision = mean(selected) if selected else 0; coverage = len(selected) / len(rows) if rows else 0
    return {"holdout_count": len(rows), "selected_count": len(selected), "base_precision": base_precision, "adjusted_precision": adjusted_precision, "coverage": coverage, "passed": coverage >= 0.5 and adjusted_precision >= base_precision}


def _now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
