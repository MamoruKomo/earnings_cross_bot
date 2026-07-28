from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any


def load_reactions(path: Path, code: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("code")) != str(code):
                continue
            rows.append(
                {
                    "code": str(row.get("code", "")),
                    "event_date": str(row.get("event_date", "")),
                    "next_open_return": _float(row.get("next_open_return")),
                    "next_close_return": _float(row.get("next_close_return")),
                    "next_high_return": _float(row.get("next_high_return")),
                    "next_low_return": _float(row.get("next_low_return")),
                    "source": str(row.get("source", "mock")),
                }
            )
    return rows


def load_production_reactions(conn: sqlite3.Connection, code: str, before_date: date) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        """
        SELECT o.code, o.event_date, o.next_open_return, o.next_close_return,
               o.next_high_return, o.next_low_return, 'observed' AS source
        FROM outcomes o
        JOIN recommendations r ON r.id=o.recommendation_id
        WHERE o.code=? AND o.event_date < ?
          AND NOT EXISTS (
            SELECT 1 FROM earnings_events e
            WHERE e.date=r.event_date AND e.code=r.code
              AND (LOWER(e.source) LIKE '%mock%' OR LOWER(e.source)='manual')
          )
        ORDER BY o.event_date DESC LIMIT 12
        """,
        (code, before_date.isoformat()),
    ).fetchall()]


def aggregate_reactions(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    if not rows:
        return (
            {
                "reaction_count": 0,
                "positive_reaction_ratio": None,
                "avg_next_open_return": None,
                "avg_next_close_return": None,
            },
            ["historical_earnings_reaction"],
        )
    open_returns = [_non_null(row.get("next_open_return")) for row in rows]
    close_returns = [_non_null(row.get("next_close_return")) for row in rows]
    open_returns = [value for value in open_returns if value is not None]
    close_returns = [value for value in close_returns if value is not None]
    positive_count = sum(1 for value in close_returns if value > 0)
    return (
        {
            "reaction_count": len(rows),
            "positive_reaction_ratio": positive_count / len(close_returns) if close_returns else None,
            "avg_next_open_return": mean(open_returns) if open_returns else None,
            "avg_next_close_return": mean(close_returns) if close_returns else None,
        },
        [],
    )


def _non_null(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
