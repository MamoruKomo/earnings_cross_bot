from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any

import requests


USER_AGENT = "earnings-cross-bot/1.0 (+https://github.com/MamoruKomo/earnings_cross_bot)"


class PublicDataError(RuntimeError):
    pass


class CalendarTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self._row = []
        elif tag in {"td", "th"} and self._row is not None: self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None: self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row: self.rows.append(self._row)
            self._row = None


def fetch_earnings_calendar(target_date: date, timeout: int = 25) -> list[dict[str, Any]]:
    response = requests.get(
        "https://www.traders.co.jp/market_jp/earnings_calendar",
        headers={"User-Agent": USER_AGENT}, timeout=timeout,
    )
    if response.status_code >= 400: raise PublicDataError(f"calendar HTTP {response.status_code}")
    parser = CalendarTableParser(); parser.feed(response.text)
    target = target_date.strftime("%m/%d")
    events: dict[str, dict[str, Any]] = {}
    for cells in parser.rows:
        if len(cells) < 4 or cells[0] != target: continue
        match = re.search(r"\(([0-9A-Z]{4})/", cells[2])
        if not match: continue
        code = match.group(1)
        name = cells[2].split("(", 1)[0].strip()
        events[code] = {
            "date": target_date.isoformat(), "code": code, "name": name,
            "announcement_time": cells[1] if cells[1] != "-" else "不明",
            "fiscal_quarter": cells[3], "source": "traders_web",
        }
    if not events: raise PublicDataError(f"calendar returned no rows for {target_date.isoformat()}")
    return sorted(events.values(), key=lambda row: row["code"])


def fetch_yahoo_prices(code: str, start: date, end: date, timeout: int = 25) -> list[dict[str, Any]]:
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.T",
        params={"period1": unix_start(start), "period2": unix_start(end) + 86400, "interval": "1d", "events": "history"},
        headers={"User-Agent": USER_AGENT}, timeout=timeout,
    )
    if response.status_code >= 400: raise PublicDataError(f"Yahoo prices HTTP {response.status_code}")
    payload = response.json().get("chart", {})
    if payload.get("error"): raise PublicDataError(str(payload["error"]))
    results = payload.get("result") or []
    if not results: raise PublicDataError("Yahoo prices returned no result")
    result = results[0]; timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for index, stamp in enumerate(timestamps):
        close = value_at(quote.get("close"), index); volume = value_at(quote.get("volume"), index)
        if close is None: continue
        rows.append({
            "date": datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(), "code": code,
            "open": value_at(quote.get("open"), index), "high": value_at(quote.get("high"), index),
            "low": value_at(quote.get("low"), index), "close": close, "volume": volume,
            "turnover_value": close * volume if volume is not None else None, "source": "yahoo_finance",
        })
    if not rows: raise PublicDataError("Yahoo prices returned no usable rows")
    return rows


def fetch_traders_financials(code: str, timeout: int = 25) -> list[dict[str, Any]]:
    response = requests.get(
        f"https://www.traders.co.jp/stocks/{code}/achievement",
        headers={"User-Agent": USER_AGENT}, timeout=timeout,
    )
    if response.status_code >= 400: raise PublicDataError(f"financials HTTP {response.status_code}")
    text = response.text
    revenue, revenue_yoy = metric(text, "売上高")
    operating_profit, operating_yoy = metric(text, "営業利益")
    ordinary_profit, _ = metric(text, "経常利益")
    net_income, _ = metric(text, "純利益")
    if revenue is None and operating_profit is None: raise PublicDataError("financial table not found")
    return [{
        "code": code, "disclosed_date": "", "fiscal_quarter": "forecast",
        "revenue": revenue, "revenue_yoy": revenue_yoy, "operating_profit": operating_profit,
        "operating_profit_yoy": operating_yoy, "ordinary_profit": ordinary_profit, "net_income": net_income,
        "operating_margin": operating_profit / revenue if operating_profit is not None and revenue else None,
        "operating_margin_change": None, "full_year_revenue_forecast": revenue,
        "full_year_operating_profit_forecast": operating_profit, "cumulative_revenue": None,
        "cumulative_operating_profit": None, "theme_score": None, "risk_notes": "",
    }]


def metric(text: str, label: str) -> tuple[float | None, float | None]:
    pattern = rf"<th[^>]*>\s*{re.escape(label)}(?:<br[^>]*>.*?)?</th>\s*<td[^>]*>(.*?)</td>"
    match = re.search(pattern, text, re.S)
    if not match: return None, None
    cell = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
    numbers = re.findall(r"[+-]?[\d,]+(?:\.\d+)?%?", cell)
    value = parse_number(numbers[0]) if numbers else None
    yoy = parse_number(numbers[1], percent=True) if len(numbers) > 1 and "%" in numbers[1] else None
    return value, yoy


def parse_number(value: str, percent: bool = False) -> float | None:
    try:
        number = float(value.replace(",", "").replace("%", ""))
        return number / 100.0 if percent else number * 1_000_000
    except (TypeError, ValueError): return None


def value_at(values: list[Any] | None, index: int) -> float | None:
    if not values or index >= len(values) or values[index] is None: return None
    return float(values[index])


def unix_start(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())
