from __future__ import annotations

import argparse

from src import db
from src.config import load_config
from src.trading_calendar import parse_date, today_jst
from src.weekly_reviewer import render_rules_suggestion, summarize_week, week_range


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Review date in YYYY-MM-DD")
    args = parser.parse_args()
    cfg = load_config()
    target_date = parse_date(args.date) if args.date else today_jst(cfg.timezone)
    week_start, week_end = week_range(target_date)

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    outcomes = db.fetch_outcomes_between(conn, week_start.isoformat(), week_end.isoformat())
    review = summarize_week(outcomes, week_start, week_end)
    db.insert_weekly_review(conn, week_start.isoformat(), week_end.isoformat(), review)
    conn.commit()

    cfg.rules_suggestion_path.write_text(render_rules_suggestion(review), encoding="utf-8")
    print(f"[weekly] recommendations={review['recommendation_count']} win={review['win']} lose={review['lose']} neutral={review['neutral']}")


if __name__ == "__main__":
    main()

