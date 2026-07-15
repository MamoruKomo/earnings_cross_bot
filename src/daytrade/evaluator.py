from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.daytrade.storage import connect, pending_candidates, save_outcome
from src.daytrade.learner import train, write_profile
from src.config import load_yaml
from src.daytrade.data_provider import fetch_yahoo_intraday


def evaluate_day(root: Path, target_date: date) -> dict[str, Any]:
    conn = connect(root / "data" / "daytrade.db"); rows = pending_candidates(conn, target_date.isoformat()); outcomes = []
    for row in rows:
        features = json.loads(row["features_json"]); reference = features.get("price") or features.get("open")
        intraday, _ = fetch_yahoo_intraday(row["code"]); as_of = features.get("data_as_of")
        bars = _post_selection_bars(intraday, target_date, as_of)
        if not bars or not reference: continue
        highs = [item["high"] for item in bars if item.get("high") is not None]; lows = [item["low"] for item in bars if item.get("low") is not None]
        if not highs or not lows: continue
        high = max(highs); low = min(lows); close = bars[-1]["close"]
        max_up = high / reference - 1; max_down = low / reference - 1; close_return = close / reference - 1
        target_hit = max_up is not None and max_up >= 0.03; stop_hit = max_down is not None and max_down <= -0.02
        analysis = analyze_miss(target_hit, stop_hit, features, close_return)
        outcome = {"reference_price": reference, "high": high, "low": low, "close": close, "max_up": max_up, "max_down": max_down, "close_return": close_return, "target_hit": target_hit, "stop_hit": stop_hit, "analysis": analysis}
        save_outcome(conn, row, outcome); outcomes.append({"code": row["code"], **outcome})
    conn.commit()
    profile = train(conn, load_yaml(root / "config" / "daytrade_rules.yaml"))
    write_profile(conn, profile, root / "data" / "daytrade_learning_profile.json")
    return {"date": target_date.isoformat(), "evaluated": len(outcomes), "outcomes": outcomes, "learning": profile}


def analyze_miss(target_hit: bool, stop_hit: bool, features: dict[str, Any], close_return: float) -> dict[str, Any]:
    reasons = []
    if not target_hit:
        if (features.get("gap_rate") or 0) > 0.05: reasons.append("ギャップ過大で上値余地が縮小")
        if not features.get("above_vwap"): reasons.append("選定時にVWAPを回復していなかった")
        if (features.get("volume_ratio") or 0) < 1.0: reasons.append("出来高が継続しなかった")
        if not reasons: reasons.append("材料またはテーマの資金流入が持続しなかった")
    return {"prediction_correct": target_hit, "stop_hit": stop_hit, "close_return": close_return, "miss_reasons": reasons}


def _post_selection_bars(rows: list[dict[str, Any]], target_date: date, as_of: str | None) -> list[dict[str, Any]]:
    cutoff = datetime.fromisoformat(as_of) if as_of else None
    output = []
    for row in rows:
        try: stamp = datetime.fromisoformat(row["datetime"])
        except (KeyError, ValueError): continue
        if stamp.astimezone(ZoneInfo("Asia/Tokyo")).date() != target_date: continue
        if cutoff is not None and stamp <= cutoff: continue
        output.append(row)
    return output
