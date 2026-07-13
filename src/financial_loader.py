from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from src.jquants_client import JQuantsClient, JQuantsError
from src.public_data_client import PublicDataError, fetch_traders_financials


def fetch_or_load_financials(
    code: str,
    as_of_date: date,
    mock_path: Path,
    client: JQuantsClient | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if client and client.enabled():
        try:
            rows = client.fetch_statements(code, end=as_of_date)
            if rows:
                return [normalize_statement(row, code) for row in rows], "jquants"
        except JQuantsError as exc:
            print(f"[financials] J-Quants fallback to mock for {code}: {exc}")

    mock = load_mock_financials(mock_path, code)
    if mock: return mock, "mock"
    try:
        return fetch_traders_financials(code), "traders_web"
    except PublicDataError as exc:
        print(f"[financials] public financials unavailable for {code}: {exc}")
        return [], "missing"


def load_mock_financials(path: Path, code: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("code")) == str(code):
                rows.append(normalize_statement(row, code))
    return rows


def normalize_statement(row: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "code": str(row.get("code") or row.get("LocalCode") or row.get("Code") or code),
        "disclosed_date": _date_string(row.get("disclosed_date") or row.get("DisclosedDate")),
        "fiscal_quarter": str(row.get("fiscal_quarter") or row.get("TypeOfCurrentPeriod") or ""),
        "revenue": _float(row.get("revenue") or row.get("NetSales") or row.get("OperatingRevenue")),
        "revenue_yoy": _float(row.get("revenue_yoy")),
        "operating_profit": _float(row.get("operating_profit") or row.get("OperatingProfit")),
        "operating_profit_yoy": _float(row.get("operating_profit_yoy")),
        "ordinary_profit": _float(row.get("ordinary_profit") or row.get("OrdinaryProfit")),
        "net_income": _float(row.get("net_income") or row.get("Profit")),
        "operating_margin": _float(row.get("operating_margin")),
        "operating_margin_change": _float(row.get("operating_margin_change")),
        "full_year_revenue_forecast": _float(row.get("full_year_revenue_forecast") or row.get("ForecastNetSales")),
        "full_year_operating_profit_forecast": _float(
            row.get("full_year_operating_profit_forecast") or row.get("ForecastOperatingProfit")
        ),
        "cumulative_revenue": _float(row.get("cumulative_revenue")),
        "cumulative_operating_profit": _float(row.get("cumulative_operating_profit")),
        "theme_score": _float(row.get("theme_score")),
        "risk_notes": str(row.get("risk_notes") or ""),
    }


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_string(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]
