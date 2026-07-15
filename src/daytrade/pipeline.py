from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import load_yaml
from src.daytrade.data_provider import fetch_market_rows, load_universe
from src.daytrade.features import build_features
from src.daytrade.news import collect_news, news_by_code
from src.daytrade.learner import adjusted_rules
from src.daytrade.notifier import send_ranking
from src.daytrade.reasoner import build_comment
from src.daytrade.scoring import score_candidate, select_ranked
from src.daytrade.storage import connect, notification_sent, save_run


def run_ranking(root: Path, target_date: date, post_slack: bool = True) -> dict[str, Any]:
    rules = load_yaml(root / "config" / "daytrade_rules.yaml")
    rules = adjusted_rules(rules, root / "data" / "daytrade_learning_profile.json"); themes = rules.get("themes", {})
    universe = load_universe(root); market_rows = fetch_market_rows(universe, target_date)
    news_map = news_by_code(collect_news(root, target_date, themes, universe)); scored = []
    for stock in market_rows:
        if stock.get("error"): continue
        features = build_features(stock); items = news_map.get(stock["code"], [])
        matched = _stock_themes(stock, items, themes); score = score_candidate(features, items, matched, rules)
        row = {"code": stock["code"], "name": stock.get("name", ""), "themes": matched or ["その他"], "features": features, "news": items, **score}
        row["comment"] = build_comment(row); scored.append(row)
    selected = select_ranked(scored, rules)
    for rank, row in enumerate(selected, 1): row["rank"] = rank
    payload = {"date": target_date.isoformat(), "universe_count": len(universe), "scored_count": len(scored), "candidates": selected}
    conn = connect(root / "data" / "daytrade.db"); already_sent = notification_sent(conn, target_date.isoformat())
    slack_sent = send_ranking(payload) if post_slack and not already_sent else already_sent
    save_run(conn, target_date.isoformat(), len(universe), selected, payload, status="sent" if slack_sent else "ranked")
    (root / "data" / "daytrade_latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["slack_sent"] = slack_sent
    return payload


def _stock_themes(stock: dict[str, Any], news: list[dict[str, Any]], themes: dict[str, list[str]]) -> list[str]:
    text = " ".join([stock.get("name", ""), stock.get("sector", ""), *(item.get("title", "") for item in news)])
    return [theme for theme, words in themes.items() if any(str(word).lower() in text.lower() for word in words)]
