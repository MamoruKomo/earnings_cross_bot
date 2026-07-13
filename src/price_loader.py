from __future__ import annotations

import csv
import math
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.jquants_client import JQuantsClient, JQuantsError
from src.trading_calendar import is_trading_day
from src.public_data_client import PublicDataError, fetch_yahoo_prices


def fetch_or_load_prices(
    code: str,
    start: date,
    end: date,
    mock_path: Path,
    client: JQuantsClient | None = None,
) -> list[dict[str, Any]]:
    if client and client.enabled():
        try:
            rows = client.fetch_prices(code, start, end)
            if rows:
                return _sort_prices(rows)
        except JQuantsError as exc:
            print(f"[prices] J-Quants fallback to mock for {code}: {exc}")

    try:
        public_rows = fetch_yahoo_prices(code, start, end)
        if public_rows: return _sort_prices(public_rows)
    except (PublicDataError, ValueError) as exc:
        print(f"[prices] Yahoo Finance fallback to local data for {code}: {exc}")

    mock_rows = load_mock_prices(mock_path, code, start, end)
    if len(mock_rows) >= 65:
        return _sort_prices(mock_rows)
    if os.environ.get("ALLOW_GENERATED_MOCKS", "").lower() not in {"1", "true", "yes"}:
        return _sort_prices(mock_rows)
    generated = generate_mock_prices(code, start, end)
    merged = {row["date"]: row for row in generated}
    merged.update({row["date"]: row for row in mock_rows})
    return _sort_prices(merged.values())


def load_mock_prices(path: Path, code: str, start: date, end: date) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("code")) != str(code):
                continue
            row_date = date.fromisoformat(str(row["date"]))
            if start <= row_date <= end:
                rows.append(normalize_price_row(row))
    return rows


def generate_mock_prices(code: str, start: date, end: date) -> list[dict[str, Any]]:
    seed = sum(ord(char) for char in str(code))
    known_base = {
        "7203": 2900,
        "6758": 14500,
        "9984": 7600,
    }
    base = known_base.get(str(code), 900 + (seed % 90) * 35)
    trend = 0.0008 + (seed % 7) * 0.00015
    rows: list[dict[str, Any]] = []
    current = start
    index = 0
    while current <= end:
        if is_trading_day(current):
            wave = math.sin(index / 4.0 + seed) * 0.012
            close = base * (1 + trend * index + wave)
            open_price = close * (1 - 0.004 + math.sin(index / 3.0) * 0.003)
            high = max(open_price, close) * 1.012
            low = min(open_price, close) * 0.988
            volume = 300000 + (seed % 40) * 18000 + index * 700
            rows.append(
                {
                    "date": current.isoformat(),
                    "code": str(code),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": round(volume, 0),
                    "turnover_value": round(volume * close, 0),
                    "source": "mock_generated",
                }
            )
            index += 1
        current += timedelta(days=1)
    return rows


def normalize_price_row(row: dict[str, Any]) -> dict[str, Any]:
    close = _float(row.get("close"))
    volume = _float(row.get("volume"))
    turnover = _float(row.get("turnover_value"))
    if turnover is None and close is not None and volume is not None:
        turnover = close * volume
    return {
        "date": str(row.get("date", ""))[:10],
        "code": str(row.get("code", "")),
        "open": _float(row.get("open")),
        "high": _float(row.get("high")),
        "low": _float(row.get("low")),
        "close": close,
        "volume": volume,
        "turnover_value": turnover,
        "source": str(row.get("source", "mock")),
    }


def find_price_on_or_before(rows: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    sorted_rows = _sort_prices(rows)
    for row in reversed(sorted_rows):
        if date.fromisoformat(row["date"]) <= target:
            return row
    return None


def find_price_on(rows: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    target_iso = target.isoformat()
    for row in rows:
        if row["date"] == target_iso:
            return row
    return None


def _sort_prices(rows: Any) -> list[dict[str, Any]]:
    return sorted([dict(row) for row in rows if row.get("date")], key=lambda row: row["date"])


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
