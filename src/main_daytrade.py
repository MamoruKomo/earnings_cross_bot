from __future__ import annotations

import argparse

from src.config import ROOT_DIR
from src.daytrade.evaluator import evaluate_day
from src.daytrade.pipeline import run_ranking
from src.trading_calendar import parse_date, today_jst


def main() -> None:
    parser = argparse.ArgumentParser(description="Japanese equity day-trade ranking")
    parser.add_argument("command", choices=("rank", "evaluate"))
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--no-slack", action="store_true")
    args = parser.parse_args(); target = parse_date(args.date) if args.date else today_jst("Asia/Tokyo")
    result = run_ranking(ROOT_DIR, target, post_slack=not args.no_slack) if args.command == "rank" else evaluate_day(ROOT_DIR, target)
    print(f"[daytrade] command={args.command} date={target} count={len(result.get('candidates') or result.get('outcomes') or [])} slack_sent={result.get('slack_sent')}")


if __name__ == "__main__": main()
