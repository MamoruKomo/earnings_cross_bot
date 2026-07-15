from __future__ import annotations

import math
from datetime import datetime
from statistics import mean, pstdev
from typing import Any
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


def build_features(stock: dict[str, Any]) -> dict[str, Any]:
    daily = stock.get("daily") or []
    intraday = stock.get("intraday") or []
    latest = _latest_jst_session(intraday)
    session_date = _session_date(latest)
    completed_daily = [row for row in daily if not session_date or str(row.get("date")) < session_date]
    closes = [float(row["close"]) for row in completed_daily if row.get("close") is not None]
    volumes = [float(row["volume"]) for row in completed_daily if row.get("volume") is not None]
    previous_close = closes[-1] if closes else _number(stock.get("quote_meta", {}).get("previous_close"))
    last = _number(latest[-1].get("close")) if latest else _number(stock.get("quote_meta", {}).get("regular_market_price"))
    open_price = _number(latest[0].get("open")) if latest else None
    current_volume = sum(_number(row.get("volume")) or 0 for row in latest) if latest else None
    avg_volume = mean(volumes[-20:]) if volumes else None
    vwap = _vwap(latest)
    atr = _atr(daily, 14)
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
    ma5 = mean(closes[-5:]) if len(closes) >= 5 else None
    ma20 = mean(closes[-20:]) if len(closes) >= 20 else None
    macd = _ema(closes, 12) - _ema(closes, 26) if len(closes) >= 26 else None
    rsi = _rsi(closes, 14)
    recent_high = max(closes[-20:]) if closes else None
    projected_volume_ratio = _projected_volume_ratio(current_volume, avg_volume, latest)
    turnover = last * current_volume if last is not None and current_volume is not None else None
    projected_turnover = last * avg_volume * projected_volume_ratio if last is not None and avg_volume is not None and projected_volume_ratio is not None else turnover
    return {
        "price": last, "previous_close": previous_close,
        "change_rate": _ratio(last, previous_close), "gap_rate": _ratio(open_price, previous_close),
        "open": open_price, "volume": current_volume, "avg_volume_20d": avg_volume,
        "volume_ratio": projected_volume_ratio, "turnover": turnover, "projected_turnover": projected_turnover,
        "market_cap": stock.get("quote_meta", {}).get("market_cap"), "vwap": vwap,
        "atr": atr, "atr_rate": atr / previous_close if atr is not None and previous_close else None,
        "volatility_20d": pstdev(returns[-20:]) * math.sqrt(252) if len(returns) >= 5 else None,
        "ma5": ma5, "ma20": ma20, "above_ma5": last > ma5 if last is not None and ma5 is not None else None,
        "above_ma20": last > ma20 if last is not None and ma20 is not None else None,
        "above_vwap": last > vwap if last is not None and vwap is not None else None,
        "macd": macd, "rsi": rsi,
        "breakout_20d": last > recent_high if last is not None and recent_high is not None else None,
        "high_update": last >= recent_high if last is not None and recent_high is not None else None,
        "box_breakout": _box_breakout(closes, last),
        "intraday_high": max((_number(row.get("high")) or -math.inf) for row in latest) if latest else None,
        "intraday_low": min((_number(row.get("low")) or math.inf) for row in latest) if latest else None,
        "data_as_of": latest[-1].get("datetime") if latest else None,
        "unavailable": ["margin_interest", "short_ratio", "pts", "order_book"],
    }


def _latest_jst_session(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    dated = []
    for row in rows:
        try: day = datetime.fromisoformat(row["datetime"]).astimezone(JST).date().isoformat()
        except (KeyError, ValueError): continue
        dated.append((day, row))
    latest_day = max((day for day, _ in dated), default=None)
    return [row for day, row in dated if day == latest_day]


def _session_date(rows: list[dict[str, Any]]) -> str | None:
    if not rows: return None
    try: return datetime.fromisoformat(rows[-1]["datetime"]).astimezone(JST).date().isoformat()
    except (KeyError, ValueError): return None


def _vwap(rows: list[dict[str, Any]]) -> float | None:
    values = []
    for row in rows:
        volume = _number(row.get("volume")); high = _number(row.get("high")); low = _number(row.get("low")); close = _number(row.get("close"))
        if volume and high is not None and low is not None and close is not None: values.append((((high + low + close) / 3), volume))
    total = sum(volume for _, volume in values)
    return sum(price * volume for price, volume in values) / total if total else None


def _atr(rows: list[dict[str, Any]], period: int) -> float | None:
    values = []
    for index in range(1, len(rows)):
        high = _number(rows[index].get("high")); low = _number(rows[index].get("low")); prev = _number(rows[index - 1].get("close"))
        if high is not None and low is not None and prev is not None: values.append(max(high - low, abs(high - prev), abs(low - prev)))
    return mean(values[-period:]) if values else None


def _ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1); result = values[0]
    for value in values[1:]: result = value * alpha + result * (1 - alpha)
    return result


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period: return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gains = mean(max(0, value) for value in changes); losses = mean(max(0, -value) for value in changes)
    return 100.0 if losses == 0 else 100 - (100 / (1 + gains / losses))


def _projected_volume_ratio(current: float | None, average: float | None, rows: list[dict[str, Any]]) -> float | None:
    if current is None or not average or not rows: return None
    try: stamp = datetime.fromisoformat(rows[-1]["datetime"]).astimezone(JST); minutes = max(5, (stamp.hour * 60 + stamp.minute) - 540)
    except (KeyError, ValueError): minutes = 30
    return (current * 300 / min(300, minutes)) / average


def _box_breakout(closes: list[float], last: float | None) -> bool | None:
    if last is None or len(closes) < 20: return None
    recent = closes[-20:]; width = (max(recent) - min(recent)) / mean(recent)
    return width <= 0.08 and last >= max(recent)


def _ratio(value: float | None, base: float | None) -> float | None:
    return value / base - 1 if value is not None and base else None


def _number(value: Any) -> float | None:
    try: return float(value) if value is not None else None
    except (TypeError, ValueError): return None
