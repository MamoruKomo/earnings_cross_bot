from __future__ import annotations

import csv
from datetime import date, time
from pathlib import Path
from typing import Any

from src.jquants_client import JQuantsClient, JQuantsError
from src.public_data_client import PublicDataError, fetch_earnings_calendar


def load_events_for_date(path: Path, target_date: date, client: JQuantsClient | None = None) -> list[dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}

    if client and client.enabled():
        try:
            for event in client.fetch_earnings_announcements(target_date):
                if event.get("code"):
                    events[event["code"]] = event
        except JQuantsError as exc:
            print(f"[calendar] J-Quants calendar fallback to CSV: {exc}")

    for event in load_manual_calendar(path, target_date):
        # Manual rows can fill gaps or override incomplete API fields.
        events[event["code"]] = {**events.get(event["code"], {}), **event}

    if not events:
        try:
            for event in fetch_earnings_calendar(target_date): events[event["code"]] = event
            print(f"[calendar] loaded {len(events)} events from Traders Web")
        except PublicDataError as exc:
            print(f"[calendar] public calendar unavailable: {exc}")

    return sorted(events.values(), key=lambda row: row.get("code", ""))


def load_manual_calendar(path: Path, target_date: date) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("date") == target_date.isoformat():
                rows.append(
                    {
                        "date": row.get("date", ""),
                        "code": str(row.get("code", "")).strip(),
                        "name": str(row.get("name", "")).strip(),
                        "announcement_time": str(row.get("announcement_time", "")).strip() or "不明",
                        "fiscal_quarter": str(row.get("fiscal_quarter", "")).strip(),
                        "source": str(row.get("source", "manual")).strip() or "manual",
                    }
                )
    return rows


def is_after_close_announcement(announcement_time: str | None) -> tuple[bool, str | None]:
    value = (announcement_time or "").strip()
    if not value or value in {"不明", "unknown", "Unknown", "-"}:
        return True, "announcement_time_unknown"
    parsed = _parse_time(value)
    if parsed is None:
        return True, "announcement_time_unknown"
    if parsed < time(15, 0):
        return False, "intraday_earnings_excluded"
    return True, None


def _parse_time(value: str) -> time | None:
    cleaned = value.replace("以降", "").strip()
    try:
        hour, minute = cleaned.split(":", 1)
        return time(int(hour), int(minute[:2]))
    except (ValueError, TypeError):
        return None
