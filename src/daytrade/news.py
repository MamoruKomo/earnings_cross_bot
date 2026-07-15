from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import requests

from src.public_data_client import USER_AGENT


POSITIVE = ("上方修正", "増益", "最高益", "受注", "採用", "提携", "承認", "増配", "自社株買い", "黒字")
NEGATIVE = ("下方修正", "減益", "赤字", "中止", "不正", "行政処分", "希薄化", "訴訟", "減配")


def collect_news(root: Path, target_date: date, themes: dict[str, list[str]], universe: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    data_dir = root / "market_intelligence" / "docs" / "data"
    items: list[dict[str, Any]] = []
    for path, source in ((data_dir / "tdnet.json", "TDnet"), (data_dir / "news.json", "market_news")):
        payload = _json(path)
        raw_items = payload.get("items") or payload.get("disclosures") or []
        for item in raw_items:
            stamp = str(item.get("date") or item.get("published_at") or item.get("datetime") or "")
            if stamp[:10] < target_date.isoformat(): continue
            title = str(item.get("title_ja") or item.get("title") or "")
            items.append(analyze_news({"source": source, "code": str(item.get("code") or ""), "title": title, "url": item.get("url")}, themes))
    briefs = _json(data_dir / "briefs.json").get("briefs") or []
    for brief in briefs:
        if str(brief.get("date")) != target_date.isoformat(): continue
        text = " / ".join([str(brief.get("headline") or ""), *(brief.get("summary_bullets") or [])])
        for code in brief.get("tickers") or []:
            items.append(analyze_news({"source": "market_brief", "code": str(code), "title": text, "url": brief.get("url")}, themes))
    items.extend(fetch_public_headlines(universe or [], themes))
    return items


def fetch_public_headlines(universe: list[dict[str, str]], themes: dict[str, list[str]], workers: int = 6) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_stock_headlines, item, themes): item for item in universe if item.get("name")}
        for future in as_completed(futures):
            try: output.extend(future.result())
            except Exception: continue
    return output


def _fetch_stock_headlines(stock: dict[str, str], themes: dict[str, list[str]]) -> list[dict[str, Any]]:
    query = f'"{stock["name"]}" (site:prtimes.jp OR site:nikkei.com OR site:kabutan.jp) when:2d'
    response = requests.get("https://news.google.com/rss/search", params={"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"}, headers={"User-Agent": USER_AGENT}, timeout=12)
    response.raise_for_status(); root = ET.fromstring(response.content); rows = []
    for item in root.findall("./channel/item")[:5]:
        title = item.findtext("title") or ""; link = item.findtext("link") or ""; source = _source_label(title, link)
        rows.append(analyze_news({"source": source, "code": stock["code"], "title": title, "url": link}, themes))
    return rows


def _source_label(title: str, link: str) -> str:
    text = f"{title} {link}".lower()
    if "pr times" in text or "prtimes" in text: return "PR TIMES"
    if "日本経済新聞" in text or "nikkei" in text: return "日経"
    if "株探" in text or "kabutan" in text: return "Kabutan"
    return "theme_news"


def analyze_news(item: dict[str, Any], themes: dict[str, list[str]]) -> dict[str, Any]:
    text = str(item.get("title") or "")
    positive = [word for word in POSITIVE if word in text]
    negative = [word for word in NEGATIVE if word in text]
    sentiment = "positive" if len(positive) > len(negative) else "negative" if len(negative) > len(positive) else "neutral"
    matched_themes = [theme for theme, words in themes.items() if any(str(word).lower() in text.lower() for word in words)]
    return {**item, "sentiment": sentiment, "themes": matched_themes, "summary": text[:180], "signals": positive + negative}


def news_by_code(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("code"): output.setdefault(str(item["code"]), []).append(item)
    return output


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")); return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError): return {}
