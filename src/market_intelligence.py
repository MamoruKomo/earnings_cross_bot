from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_market_intelligence(root: Path) -> dict[str, Any]:
    data_dir = root / "docs" / "data"
    briefs_store = _load_json(data_dir / "briefs.json", {"briefs": []})
    tdnet_store = _load_json(data_dir / "tdnet.json", {"items": []})
    watch_store = _load_json(data_dir / "watchlist_snapshots.json", {"snapshots": []})
    fundamentals_store = _load_json(data_dir / "fundamentals_rankings.json", {"months": {}})

    briefs = _dict_list(briefs_store.get("briefs"))
    briefs.sort(key=lambda item: str(item.get("date") or ""), reverse=True)

    disclosures = _dict_list(tdnet_store.get("items"))
    disclosures.sort(key=lambda item: str(item.get("datetime_jst") or ""), reverse=True)

    snapshots = _dict_list(watch_store.get("snapshots"))
    snapshots.sort(key=lambda item: str(item.get("datetime_jst") or ""), reverse=True)
    latest_snapshot = snapshots[0] if snapshots else None

    latest_month = str(fundamentals_store.get("latest_month") or "")
    months = fundamentals_store.get("months")
    latest_fundamentals = months.get(latest_month, {}) if isinstance(months, dict) else {}

    return {
        "updated_at": _latest_timestamp(briefs_store, tdnet_store, watch_store, fundamentals_store),
        "latest_brief": briefs[0] if briefs else None,
        "recent_briefs": briefs[:30],
        "disclosures": disclosures[:200],
        "latest_watchlist": latest_snapshot,
        "fundamentals": {
            "month": latest_month,
            "generated_at": latest_fundamentals.get("generated_at") if isinstance(latest_fundamentals, dict) else None,
            "metrics": latest_fundamentals.get("metrics", {}) if isinstance(latest_fundamentals, dict) else {},
        },
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
