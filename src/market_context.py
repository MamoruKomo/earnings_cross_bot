from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


def load_sector_context(repo_root: Path, code: str, target_date: date) -> tuple[dict[str, Any], list[str]]:
    sector = _lookup_sector(repo_root, code)
    brief = _latest_brief(repo_root, target_date)
    if not brief:
        return {"sector": sector, "mood": "unknown", "summary": "市場朝刊を取得できず地合い不明"}, ["sector_mood"]

    market_return = _market_return(brief)
    leaders = brief.get("sector_leaders") or _sector_names(brief, "+")
    laggards = brief.get("sector_laggards") or _sector_names(brief, "-")
    mood = "neutral"
    sector_return = None
    for row in leaders:
        name, value = _sector_row(row)
        if _same_sector(sector, name):
            mood, sector_return = "strong", value
            break
    if mood == "neutral":
        for row in laggards:
            name, value = _sector_row(row)
            if _same_sector(sector, name):
                mood, sector_return = "weak", value
                break
    if not sector:
        mood = "market_only"

    market_text = "市場は不明" if market_return is None else f"日経平均 {market_return:+.2%}"
    sector_text = f"{sector}は{_mood_label(mood)}" if sector else "業種分類は未取得"
    return {
        "sector": sector,
        "mood": mood,
        "market_return": market_return,
        "sector_return": sector_return,
        "leaders": [_sector_row(row)[0] for row in leaders[:3]],
        "laggards": [_sector_row(row)[0] for row in laggards[:3]],
        "brief_date": brief.get("date"),
        "summary": f"{market_text}、{sector_text}",
    }, ([] if sector else ["sector_classification"])


def _lookup_sector(repo_root: Path, code: str) -> str:
    code = str(code).rstrip("0") if len(str(code)) == 5 else str(code)
    paths = [
        repo_root / "market_intelligence/docs/data/fundamentals.json",
        repo_root / "market_intelligence/docs/data/fundamentals_rankings.json",
        repo_root / "market_intelligence/docs/data/tickers_master.json",
        repo_root / "market_intelligence/docs/data/watchlist.json",
        repo_root / "market_intelligence/docs/data/hidden_gems.json",
    ]
    for path in paths:
        for item in _walk_items(_read_json(path)):
            item_code = str(item.get("code", ""))
            if item_code.rstrip("0") == code.rstrip("0") and item.get("sector"):
                return str(item["sector"])
    return ""


def _latest_brief(repo_root: Path, target_date: date) -> dict[str, Any] | None:
    data = _read_json(repo_root / "market_intelligence/docs/data/briefs.json")
    rows = data.get("briefs", []) if isinstance(data, dict) else []
    usable = [row for row in rows if str(row.get("date", "")) <= target_date.isoformat()]
    return max(usable, key=lambda row: str(row.get("date", "")), default=None)


def _market_return(brief: dict[str, Any]) -> float | None:
    for text in brief.get("summary_bullets", []):
        match = re.search(r"日経平均.*?\(([+-]?\d+(?:\.\d+)?)%\)", str(text))
        if match:
            return float(match.group(1)) / 100.0
    return None


def _sector_names(brief: dict[str, Any], sign: str) -> list[dict[str, Any]]:
    for text in brief.get("summary_bullets", []):
        if not str(text).startswith("業種:"):
            continue
        pattern = r"\+([^/]+)" if sign == "+" else r"-([^/]+)"
        match = re.search(pattern, str(text))
        return [{"name": match.group(1).strip(), "return": None}] if match else []
    return []


def _sector_row(row: Any) -> tuple[str, float | None]:
    if isinstance(row, str):
        return row, None
    value = row.get("return", row.get("pct"))
    return str(row.get("name", "")), (float(value) if value is not None else None)


def _same_sector(left: str, right: str) -> bool:
    normalize = lambda value: str(value).replace("・", "").replace("、", "").removesuffix("業")
    return bool(left and right and normalize(left) == normalize(right))


def _mood_label(mood: str) -> str:
    return {"strong": "上位で追い風", "weak": "下位で逆風", "neutral": "中立", "market_only": "不明"}.get(mood, "不明")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _walk_items(value: Any):
    if isinstance(value, dict):
        if "code" in value:
            yield value
        for child in value.values():
            yield from _walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_items(child)
