from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def load_market_intelligence(root: Path, now: datetime | None = None) -> dict[str, Any]:
    data_dir = root / "docs" / "data"
    briefs_store = _load_json(data_dir / "briefs.json", {"briefs": []})
    watch_store = _load_json(data_dir / "watchlist_snapshots.json", {"snapshots": []})
    fundamentals_store = _load_json(data_dir / "fundamentals_rankings.json", {"months": {}})

    briefs = _dict_list(briefs_store.get("briefs"))
    briefs.sort(key=lambda item: str(item.get("date") or ""), reverse=True)

    snapshots = _dict_list(watch_store.get("snapshots"))
    snapshots.sort(key=lambda item: str(item.get("datetime_jst") or ""), reverse=True)
    latest_snapshot = snapshots[0] if snapshots else None

    latest_month = str(fundamentals_store.get("latest_month") or "")
    months = fundamentals_store.get("months")
    latest_fundamentals = months.get(latest_month, {}) if isinstance(months, dict) else {}
    now = now or datetime.now(timezone.utc)
    health = _market_health(
        now,
        latest_brief=briefs[0] if briefs else None,
        latest_snapshot=latest_snapshot,
        latest_fundamentals=latest_fundamentals if isinstance(latest_fundamentals, dict) else {},
    )

    return {
        "updated_at": _latest_timestamp(briefs_store, watch_store, fundamentals_store),
        "latest_brief": briefs[0] if briefs else None,
        "recent_briefs": briefs[:30],
        "latest_watchlist": latest_snapshot,
        "fundamentals": {
            "month": latest_month,
            "generated_at": latest_fundamentals.get("generated_at") if isinstance(latest_fundamentals, dict) else None,
            "metrics": latest_fundamentals.get("metrics", {}) if isinstance(latest_fundamentals, dict) else {},
        },
        "health": health,
    }


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return value if isinstance(value, dict) else default


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _latest_timestamp(*stores: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    for store in stores:
        for key in ("updated_at", "last_checked_jst"):
            value = store.get(key)
            if value:
                candidates.append(str(value))
    return max(candidates, default=None)


def _market_health(
    now: datetime,
    *,
    latest_brief: dict[str, Any] | None,
    latest_snapshot: dict[str, Any] | None,
    latest_fundamentals: dict[str, Any],
) -> dict[str, Any]:
    brief_date = str((latest_brief or {}).get("date") or "")
    brief_updated = f"{brief_date}T08:20:00+09:00" if brief_date else None
    sources = [
        _source_health("morning_brief", "市場朝刊", brief_updated, now, 30, 72),
        _source_health("watchlist", "ウォッチリスト", (latest_snapshot or {}).get("datetime_jst"), now, 36, 72),
        _source_health("fundamentals", "ファンダメンタルズ", latest_fundamentals.get("generated_at"), now, 840, 1200),
    ]
    critical = {"morning_brief", "watchlist"}
    if any(item["key"] in critical and item["status"] in {"stale", "missing"} for item in sources):
        overall = "stale"
    elif any(item["status"] != "fresh" for item in sources):
        overall = "warning"
    else:
        overall = "fresh"
    return {"overall": overall, "sources": sources}


def _source_health(
    key: str,
    label: str,
    updated_at: Any,
    now: datetime,
    warning_hours: float,
    stale_hours: float,
) -> dict[str, Any]:
    timestamp = _parse_datetime(updated_at)
    if timestamp is None:
        return {"key": key, "label": label, "status": "missing", "updated_at": None, "age_hours": None, "message": "データがありません"}
    age_hours = max(0.0, (now.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds() / 3600)
    if age_hours >= stale_hours:
        status, message = "stale", "更新期限を超えています。判断に使用しないでください"
    elif age_hours >= warning_hours:
        status, message = "warning", "更新時刻を確認してください"
    else:
        status, message = "fresh", "更新済み"
    return {
        "key": key,
        "label": label,
        "status": status,
        "updated_at": str(updated_at),
        "age_hours": round(age_hours, 1),
        "message": message,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    return parsed
