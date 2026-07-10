from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from src.jquants_client import JQuantsClient, JQuantsError


def fetch_or_load_supply_demand(
    code: str, as_of_date: date, manual_path: Path, client: JQuantsClient | None = None
) -> tuple[dict[str, Any], list[str]]:
    rows: list[dict[str, Any]] = []
    source = "manual"
    if client and client.enabled():
        try:
            rows = [normalize_margin(row, code, "jquants") for row in client.fetch_weekly_margin_interest(code)]
            source = "jquants"
        except JQuantsError as exc:
            print(f"[supply-demand] J-Quants fallback to CSV for {code}: {exc}")
    if not rows:
        rows = load_manual_margin(manual_path, code)
    rows = sorted((row for row in rows if row["as_of_date"] <= as_of_date.isoformat()), key=lambda row: row["as_of_date"])
    if not rows:
        return empty_supply_demand(code, as_of_date), ["supply_demand"]
    latest = dict(rows[-1]); previous = rows[-2] if len(rows) > 1 else None
    latest["source"] = source if source == "jquants" else latest.get("source", "manual")
    latest["long_weekly_change"] = relative_change(latest.get("long_margin_outstanding"), previous.get("long_margin_outstanding") if previous else None)
    latest["short_weekly_change"] = relative_change(latest.get("short_margin_outstanding"), previous.get("short_margin_outstanding") if previous else None)
    return latest, []


def load_manual_margin(path: Path, code: str) -> list[dict[str, Any]]:
    if not path.exists(): return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [normalize_margin(row, code, row.get("source") or "manual") for row in csv.DictReader(handle) if str(row.get("code")) == str(code)]


def normalize_margin(row: dict[str, Any], code: str, source: str) -> dict[str, Any]:
    long_value = number(row.get("long_margin_outstanding") or row.get("LongMarginOutstanding"))
    short_value = number(row.get("short_margin_outstanding") or row.get("ShortMarginOutstanding"))
    return {
        "code": str(row.get("code") or row.get("Code") or code)[:4],
        "as_of_date": str(row.get("as_of_date") or row.get("Date") or "")[:10],
        "long_margin_outstanding": long_value,
        "short_margin_outstanding": short_value,
        "margin_ratio": long_value / short_value if long_value is not None and short_value not in (None, 0) else None,
        "long_weekly_change": None, "short_weekly_change": None, "source": source,
    }


def empty_supply_demand(code: str, as_of_date: date) -> dict[str, Any]:
    return {"code": code, "as_of_date": as_of_date.isoformat(), "long_margin_outstanding": None,
            "short_margin_outstanding": None, "margin_ratio": None, "long_weekly_change": None,
            "short_weekly_change": None, "source": "missing"}


def relative_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0): return None
    return (current / previous) - 1.0


def number(value: Any) -> float | None:
    try: return None if value in (None, "") else float(value)
    except (TypeError, ValueError): return None
