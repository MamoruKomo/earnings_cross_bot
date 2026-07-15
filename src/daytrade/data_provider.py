from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from src.public_data_client import USER_AGENT, fetch_yahoo_prices


def load_universe(root: Path, limit: int = 80) -> list[dict[str, str]]:
    data_dir = root / "market_intelligence" / "docs" / "data"
    master = _json(data_dir / "tickers_master.json", {}).get("items") or []
    briefs = _json(data_dir / "briefs.json", {}).get("briefs") or []
    by_code = {str(row.get("code")): {"code": str(row.get("code")), "name": str(row.get("name") or ""), "sector": str(row.get("sector") or "")} for row in master if row.get("code")}
    for brief in briefs[:3]:
        for code in brief.get("tickers") or []:
            by_code.setdefault(str(code), {"code": str(code), "name": "", "sector": ""})
    return list(by_code.values())[:limit]


def fetch_market_rows(universe: list[dict[str, str]], target_date: date, workers: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_stock_data, item, target_date): item for item in universe}
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                item = futures[future]
                row = {**item, "error": str(exc), "daily": [], "intraday": [], "missing": ["market_data"]}
            rows.append(row)
    return sorted(rows, key=lambda row: row["code"])


def fetch_stock_data(item: dict[str, str], target_date: date) -> dict[str, Any]:
    daily = fetch_yahoo_prices(item["code"], target_date - timedelta(days=70), target_date)
    intraday, meta = fetch_yahoo_intraday(item["code"])
    return {**item, "daily": daily, "intraday": intraday, "quote_meta": meta, "missing": []}


def fetch_yahoo_intraday(code: str, timeout: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.T",
        params={"range": "5d", "interval": "5m", "events": "history"},
        headers={"User-Agent": USER_AGENT}, timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json().get("chart", {})
    result = (payload.get("result") or [None])[0]
    if not result:
        raise RuntimeError("Yahoo intraday returned no result")
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    rows = []
    for index, stamp in enumerate(timestamps):
        close = _at(quote.get("close"), index)
        if close is None:
            continue
        rows.append({
            "datetime": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
            "open": _at(quote.get("open"), index), "high": _at(quote.get("high"), index),
            "low": _at(quote.get("low"), index), "close": close, "volume": _at(quote.get("volume"), index),
        })
    meta = result.get("meta") or {}
    return rows, {
        "market_cap": meta.get("marketCap"), "regular_market_price": meta.get("regularMarketPrice"),
        "previous_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
        "exchange_timezone": meta.get("exchangeTimezoneName"), "source": "yahoo_finance",
    }


def _at(values: list[Any] | None, index: int) -> float | None:
    if not values or index >= len(values) or values[index] is None:
        return None
    return float(values[index])


def _json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, json.JSONDecodeError):
        return default
