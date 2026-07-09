from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from src import db
from src.config import load_config
from src.evaluator import build_outcome
from src.jquants_client import JQuantsClient
from src.llm_reasoner import analyze_outcome_lesson
from src.price_loader import fetch_or_load_prices, find_price_on, find_price_on_or_before
from src.trading_calendar import is_trading_day, next_trading_day, parse_date, today_jst


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Evaluation date in YYYY-MM-DD")
    args = parser.parse_args()
    cfg = load_config()
    evaluation_date = parse_date(args.date) if args.date else today_jst(cfg.timezone)

    conn = db.connect(cfg.db_path)
    db.init_db(conn)

    if not is_trading_day(evaluation_date):
        print(f"[evaluate] {evaluation_date.isoformat()} is not a JP trading day. skipped.")
        return

    recommendations = db.fetch_unevaluated_recommendations(conn, evaluation_date.isoformat())
    if not recommendations:
        print("[evaluate] no unevaluated recommendations.")
        return

    client = JQuantsClient.from_env()
    evaluated = 0
    for row in recommendations:
        event_date = date.fromisoformat(row["event_date"])
        expected_eval_date = next_trading_day(event_date)
        if expected_eval_date > evaluation_date:
            continue
        prices = fetch_or_load_prices(
            row["code"],
            event_date - timedelta(days=5),
            expected_eval_date,
            cfg.mock_prices_path,
            client,
        )
        db.upsert_daily_prices(conn, prices)
        event_price = find_price_on_or_before(prices, event_date)
        next_price = find_price_on(prices, expected_eval_date)
        if not event_price or not next_price:
            print(f"[evaluate] missing price data for {row['code']} {event_date} -> {expected_eval_date}")
            continue
        outcome = build_outcome(
            recommendation_id=int(row["id"]),
            code=row["code"],
            event_date=row["event_date"],
            evaluation_date=expected_eval_date.isoformat(),
            event_price=event_price,
            next_price=next_price,
            rules=cfg.rules,
        )
        outcome_id = db.insert_outcome(conn, outcome)
        recommendation = {
            "code": row["code"],
            "risk_factors": json.loads(row["risk_factors_json"] or "[]"),
        }
        lesson = analyze_outcome_lesson(recommendation, outcome)
        db.insert_lesson(conn, outcome_id, expected_eval_date.isoformat(), row["code"], lesson)
        append_lesson(cfg.lessons_path, lesson)
        evaluated += 1
    conn.commit()
    print(f"[evaluate] evaluated={evaluated}")


def append_lesson(path, lesson: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(lesson, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

