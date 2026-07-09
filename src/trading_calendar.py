from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


# Tokyo Stock Exchange is closed on weekends, year-end/new-year days, and
# Japanese public holidays. The static set below keeps the MVP dependency-free;
# J-Quants or JPX calendars can replace it later.
JP_MARKET_HOLIDAYS = {
    "2026-01-01",
    "2026-01-02",
    "2026-01-12",
    "2026-02-11",
    "2026-02-23",
    "2026-03-20",
    "2026-04-29",
    "2026-05-04",
    "2026-05-05",
    "2026-05-06",
    "2026-07-20",
    "2026-08-11",
    "2026-09-21",
    "2026-09-22",
    "2026-09-23",
    "2026-10-12",
    "2026-11-03",
    "2026-11-23",
    "2026-12-31",
    "2027-01-01",
    "2027-01-02",
    "2027-01-03",
}


def parse_date(value: str | date | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def today_jst(timezone: str = "Asia/Tokyo") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def is_trading_day(value: str | date) -> bool:
    target = parse_date(value)
    if target.weekday() >= 5:
        return False
    return target.isoformat() not in JP_MARKET_HOLIDAYS


def previous_trading_day(value: str | date, count: int = 1) -> date:
    current = parse_date(value)
    found = 0
    while found < count:
        current -= timedelta(days=1)
        if is_trading_day(current):
            found += 1
    return current


def next_trading_day(value: str | date, count: int = 1) -> date:
    current = parse_date(value)
    found = 0
    while found < count:
        current += timedelta(days=1)
        if is_trading_day(current):
            found += 1
    return current


def trading_days_between(start: str | date, end: str | date) -> list[date]:
    current = parse_date(start)
    finish = parse_date(end)
    days: list[date] = []
    while current <= finish:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days

