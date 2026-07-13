from __future__ import annotations

import argparse
from datetime import timedelta

from src import db
from src.calendar_loader import is_after_close_announcement, load_events_for_date
from src.config import load_config
from src.earnings_reaction import aggregate_reactions, load_reactions
from src.feature_engineering import compute_financial_features, compute_price_features
from src.financial_loader import fetch_or_load_financials
from src.jquants_client import JQuantsClient
from src.llm_reasoner import generate_recommendation_payload
from src.price_loader import fetch_or_load_prices
from src.scorer import score_candidate, select_recommendations
from src.supply_demand_loader import fetch_or_load_supply_demand
from src.adaptive_learner import apply_learned_weights
from src.slack_notifier import format_recommendation_message, post_message
from src.trading_calendar import is_trading_day, parse_date, today_jst


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date in YYYY-MM-DD")
    parser.add_argument("--force-post", action="store_true", help="Post even when this date was already notified")
    args = parser.parse_args()
    cfg = load_config()
    cfg.rules["scoring_weights"] = apply_learned_weights(cfg.rules, cfg.learning_profile_path)
    target_date = parse_date(args.date) if args.date else today_jst(cfg.timezone)

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    target_date_text = target_date.isoformat()

    if not args.force_post and db.notification_sent(conn, target_date_text, "morning"):
        print(f"[morning] already notified for {target_date_text}. skipped duplicate post.")
        return

    if not is_trading_day(target_date):
        print(f"[morning] {target_date.isoformat()} is not a JP trading day. skipped.")
        return

    client = JQuantsClient.from_env()
    events = load_events_for_date(cfg.manual_calendar_path, target_date, client)
    scored: list[dict] = []

    start = target_date - timedelta(days=190)
    for event in events:
        allowed, event_risk = is_after_close_announcement(event.get("announcement_time"))
        db.upsert_earnings_event(conn, event)
        if not allowed:
            print(f"[morning] exclude intraday earnings: {event['code']} {event.get('announcement_time')}")
            continue

        prices = fetch_or_load_prices(event["code"], start, target_date, cfg.mock_prices_path, client)
        db.upsert_daily_prices(conn, prices)
        price_features, price_missing = compute_price_features(prices)

        statements, financial_source = fetch_or_load_financials(event["code"], target_date, cfg.mock_financials_path, client)
        financial_features, financial_missing = compute_financial_features(statements)
        db.upsert_financial_features(
            conn,
            event["code"],
            target_date.isoformat(),
            financial_features,
            financial_missing,
            financial_source,
        )

        reactions = load_reactions(cfg.mock_reactions_path, event["code"])
        db.upsert_earnings_reactions(conn, reactions)
        reaction_features, reaction_missing = aggregate_reactions(reactions)

        supply_demand, supply_missing = fetch_or_load_supply_demand(event["code"], target_date, cfg.margin_interest_path, client)
        db.upsert_supply_demand(conn, supply_demand)

        missing = price_missing + financial_missing + reaction_missing + supply_missing
        if event_risk:
            missing.append(event_risk)
        scored.append(score_candidate(event, price_features, financial_features, reaction_features, supply_demand, missing, cfg.rules))

    selected = select_recommendations(scored, cfg.rules)
    payload = generate_recommendation_payload(conn, target_date, selected, scored, cfg.rules)
    if not events:
        payload = {
            "date": target_date_text,
            "market_note": "決算予定データを取得できなかったため、今日は判定を保留します。",
            "recommendations": [],
            "no_trade_reason": "対象銘柄が0件でした。J-Quants認証または手動決算カレンダーを確認してください。",
            "data_status": "unavailable",
        }

    candidate_by_code = {item["code"]: item for item in selected}
    for rec in payload.get("recommendations", []):
        score_details = candidate_by_code.get(rec["code"], {})
        db.insert_recommendation(
            conn,
            target_date.isoformat(),
            target_date.isoformat(),
            rec,
            score_details,
            cfg.model_version,
            cfg.rules_version,
            payload,
        )
    conn.commit()

    message = format_recommendation_message(payload)
    sent = post_message(message)
    db.record_notification(conn, target_date_text, "morning", "sent" if sent else "failed", {
        "candidate_count": len(payload.get("recommendations", [])), "data_status": payload.get("data_status", "ok")
    })
    conn.commit()
    print(f"[morning] scored={len(scored)} posted_candidates={len(payload.get('recommendations', []))}")


if __name__ == "__main__":
    main()
