from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from src import db
from src.validator import build_validation_report


def build_dashboard_data(conn: sqlite3.Connection) -> dict[str, Any]:
    recommendations = fetch_recommendation_rows(conn)
    llm_runs = fetch_recommendation_llm_runs(conn)
    generated_at = db.now_iso()

    evaluated = [row for row in recommendations if row.get("result")]
    pending = [row for row in recommendations if not row.get("result")]
    result_counts = count_results(evaluated)
    recommendation_dates = {str(row["recommendation_date"]) for row in recommendations}
    no_trade_days = count_no_trade_days(llm_runs, recommendation_dates)

    return {
        "generated_at": generated_at,
        "summary": build_summary(recommendations, evaluated, pending, result_counts, no_trade_days),
        "result_distribution": result_counts,
        "weekly": build_weekly(evaluated),
        "equity_curve": build_equity_curve(evaluated),
        "by_code": build_by_code(recommendations),
        "by_action": build_by_action(recommendations),
        "recent_outcomes": build_recent_outcomes(evaluated),
        "pending_recommendations": build_pending(pending),
        "stock_snapshots": build_stock_snapshots(conn, recommendations),
        "learning": fetch_learning_status(conn),
        "validation": build_validation_report(conn, load_rules_for_validation()),
        "latest_notification": fetch_latest_notification(conn),
        "no_trade_days": sorted(no_trade_days),
    }


def fetch_recommendation_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            r.id,
            r.recommendation_date,
            r.event_date,
            r.code,
            r.name,
            r.score,
            r.action,
            r.confidence,
            r.announcement_time,
            r.thesis,
            r.missing_data_json,
            r.risk_factors_json,
            o.evaluation_date,
            o.next_open_return,
            o.next_high_return,
            o.next_low_return,
            o.next_close_return,
            o.max_drawdown,
            o.result
        FROM recommendations r
        LEFT JOIN outcomes o ON o.recommendation_id = r.id
        ORDER BY r.recommendation_date ASC, r.score DESC, r.code ASC
        """
    ).fetchall()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["missing_data"] = parse_json_array(item.pop("missing_data_json"))
        item["risk_factors"] = parse_json_array(item.pop("risk_factors_json"))
        normalized.append(item)
    return normalized


def fetch_recommendation_llm_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT created_at, output_json FROM llm_runs WHERE run_type = 'recommendation' ORDER BY created_at ASC"
    ).fetchall()
    runs = []
    for row in rows:
        payload = parse_json_object(row["output_json"])
        if payload:
            runs.append({"created_at": row["created_at"], "output": payload})
    return runs


def build_summary(
    recommendations: list[dict[str, Any]],
    evaluated: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    result_counts: dict[str, int],
    no_trade_days: set[str],
) -> dict[str, Any]:
    evaluated_count = len(evaluated)
    win_count = result_counts["win"]
    neutral_count = result_counts["neutral"]
    lose_count = result_counts["lose"]
    close_returns = [row["next_close_return"] for row in evaluated if row.get("next_close_return") is not None]
    open_returns = [row["next_open_return"] for row in evaluated if row.get("next_open_return") is not None]
    best = max(evaluated, key=lambda row: row.get("next_close_return") or -999, default=None)
    worst = min(evaluated, key=lambda row: row.get("next_close_return") or 999, default=None)
    return {
        "recommendation_count": len(recommendations),
        "evaluated_count": evaluated_count,
        "pending_count": len(pending),
        "no_trade_day_count": len(no_trade_days),
        "win_count": win_count,
        "neutral_count": neutral_count,
        "lose_count": lose_count,
        "hit_rate": safe_ratio(win_count, evaluated_count),
        "non_loss_rate": safe_ratio(win_count + neutral_count, evaluated_count),
        "lose_rate": safe_ratio(lose_count, evaluated_count),
        "avg_next_open_return": safe_mean(open_returns),
        "avg_next_close_return": safe_mean(close_returns),
        "positive_close_rate": safe_ratio(sum(1 for value in close_returns if value > 0), len(close_returns)),
        "best": compact_result(best),
        "worst": compact_result(worst),
    }


def count_results(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "win": sum(1 for row in rows if row.get("result") == "win"),
        "neutral": sum(1 for row in rows if row.get("result") == "neutral"),
        "lose": sum(1 for row in rows if row.get("result") == "lose"),
    }


def count_no_trade_days(llm_runs: list[dict[str, Any]], recommendation_dates: set[str] | None = None) -> set[str]:
    days: set[str] = set()
    recommendation_dates = recommendation_dates or set()
    for run in llm_runs:
        output = run["output"]
        recommendations = output.get("recommendations") or []
        target_date = output.get("date")
        if target_date and not recommendations and str(target_date) not in recommendation_dates:
            days.add(str(target_date))
    return days


def build_weekly(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not row.get("evaluation_date"):
            continue
        week_start = iso_week_start(row["evaluation_date"])
        grouped[week_start].append(row)

    weekly = []
    for week_start, items in sorted(grouped.items()):
        counts = count_results(items)
        close_returns = [row["next_close_return"] for row in items if row.get("next_close_return") is not None]
        weekly.append(
            {
                "week_start": week_start,
                "count": len(items),
                "win": counts["win"],
                "neutral": counts["neutral"],
                "lose": counts["lose"],
                "hit_rate": safe_ratio(counts["win"], len(items)),
                "avg_next_close_return": safe_mean(close_returns),
            }
        )
    return weekly


def build_equity_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (row.get("evaluation_date") or "", row.get("code") or ""))
    capital = 1.0
    curve = []
    for row in ordered:
        close_return = row.get("next_close_return")
        if close_return is None:
            continue
        capital *= 1.0 + float(close_return)
        curve.append(
            {
                "date": row["evaluation_date"],
                "code": row["code"],
                "result": row["result"],
                "next_close_return": close_return,
                "cumulative_return": capital - 1.0,
            }
        )
    return curve


def build_by_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["code"]].append(row)

    output = []
    for code, items in grouped.items():
        evaluated = [row for row in items if row.get("result")]
        counts = count_results(evaluated)
        close_returns = [row["next_close_return"] for row in evaluated if row.get("next_close_return") is not None]
        latest = max(items, key=lambda row: row.get("recommendation_date") or "")
        output.append(
            {
                "code": code,
                "name": latest.get("name", ""),
                "recommendation_count": len(items),
                "evaluated_count": len(evaluated),
                "win": counts["win"],
                "neutral": counts["neutral"],
                "lose": counts["lose"],
                "hit_rate": safe_ratio(counts["win"], len(evaluated)),
                "avg_next_close_return": safe_mean(close_returns),
                "last_recommendation_date": latest.get("recommendation_date"),
            }
        )
    return sorted(output, key=lambda row: (row["evaluated_count"], row["avg_next_close_return"] or -999), reverse=True)


def build_by_action(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["action"]].append(row)
    output = []
    for action, items in grouped.items():
        evaluated = [row for row in items if row.get("result")]
        counts = count_results(evaluated)
        close_returns = [row["next_close_return"] for row in evaluated if row.get("next_close_return") is not None]
        output.append(
            {
                "action": action,
                "recommendation_count": len(items),
                "evaluated_count": len(evaluated),
                "win": counts["win"],
                "neutral": counts["neutral"],
                "lose": counts["lose"],
                "hit_rate": safe_ratio(counts["win"], len(evaluated)),
                "avg_next_close_return": safe_mean(close_returns),
            }
        )
    return sorted(output, key=lambda row: row["action"])


def build_recent_outcomes(rows: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (row.get("evaluation_date") or "", row.get("code") or ""), reverse=True)
    return [compact_result(row) for row in ordered[:limit]]


def build_pending(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (row.get("event_date") or "", row.get("code") or ""), reverse=True)
    return [
        {
            "recommendation_date": row["recommendation_date"],
            "event_date": row["event_date"],
            "code": row["code"],
            "name": row["name"],
            "score": row["score"],
            "action": row["action"],
            "confidence": row.get("confidence"),
            "announcement_time": row.get("announcement_time"),
            "thesis": row.get("thesis"),
            "risk_factors": row.get("risk_factors") or [],
            "missing_data": row.get("missing_data") or [],
        }
        for row in ordered[:limit]
    ]


def build_stock_snapshots(conn: sqlite3.Connection, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    latest_by_code = {row["code"]: row for row in recommendations}
    for code, recommendation in latest_by_code.items():
        financial = conn.execute(
            "SELECT features_json, source, as_of_date FROM financial_features WHERE code=? ORDER BY as_of_date DESC LIMIT 1", (code,)
        ).fetchone()
        demand = conn.execute(
            "SELECT * FROM supply_demand_features WHERE code=? ORDER BY as_of_date DESC LIMIT 1", (code,)
        ).fetchone()
        features = parse_json_object(financial["features_json"]) if financial else {}
        output.append({
            "code": code, "name": recommendation.get("name", ""),
            "revenue_yoy": features.get("revenue_yoy"), "operating_profit_yoy": features.get("operating_profit_yoy"),
            "operating_margin": features.get("operating_margin"), "revenue_progress_rate": features.get("revenue_progress_rate"),
            "financial_source": financial["source"] if financial else None,
            "margin_as_of_date": demand["as_of_date"] if demand else None,
            "long_margin_outstanding": demand["long_margin_outstanding"] if demand else None,
            "short_margin_outstanding": demand["short_margin_outstanding"] if demand else None,
            "margin_ratio": demand["margin_ratio"] if demand else None,
            "long_weekly_change": demand["long_weekly_change"] if demand else None,
            "supply_demand_source": demand["source"] if demand else None,
        })
    return sorted(output, key=lambda row: row["code"])


def fetch_learning_status(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT profile_json FROM learning_runs ORDER BY id DESC LIMIT 1").fetchone()
    return parse_json_object(row["profile_json"]) if row else {"status": "not_run", "sample_count": 0, "minimum_samples": 30, "message": "未実行"}


def fetch_latest_notification(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT notification_date, notification_type, status, detail_json, created_at
        FROM notification_runs
        ORDER BY created_at DESC LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    detail = parse_json_object(row["detail_json"]) or {}
    return {
        "date": row["notification_date"],
        "type": row["notification_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "candidate_count": detail.get("candidate_count"),
        "data_status": detail.get("data_status"),
    }


def load_rules_for_validation() -> dict[str, Any]:
    # Dashboard generation already runs from the repository root in production.
    try:
        import yaml
        return yaml.safe_load(Path("config/rules.yaml").read_text(encoding="utf-8")) or {}
    except (ImportError, OSError, ValueError):
        return {"learning": {"minimum_samples": 30, "validation_samples": 10}}


def write_dashboard_files(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    output_path.write_text(json_text + "\n", encoding="utf-8")


def parse_json_array(value: str | None) -> list[Any]:
    parsed = parse_json_object(value)
    return parsed if isinstance(parsed, list) else []


def parse_json_object(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def compact_result(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "recommendation_date": row.get("recommendation_date"),
        "event_date": row.get("event_date"),
        "evaluation_date": row.get("evaluation_date"),
        "code": row.get("code"),
        "name": row.get("name"),
        "score": row.get("score"),
        "action": row.get("action"),
        "result": row.get("result"),
        "next_open_return": row.get("next_open_return"),
        "next_close_return": row.get("next_close_return"),
        "max_drawdown": row.get("max_drawdown"),
    }


def iso_week_start(value: str) -> str:
    target = date.fromisoformat(value)
    return (target.fromordinal(target.toordinal() - target.weekday())).isoformat()


def safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return mean(values)


def format_timestamp(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
