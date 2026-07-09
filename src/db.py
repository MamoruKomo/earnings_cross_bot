from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS earnings_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            announcement_time TEXT,
            fiscal_quarter TEXT,
            source TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(date, code)
        );

        CREATE TABLE IF NOT EXISTS daily_prices (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            turnover_value REAL,
            source TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(code, date)
        );

        CREATE TABLE IF NOT EXISTS financial_features (
            code TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            features_json TEXT NOT NULL,
            missing_data_json TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(code, as_of_date)
        );

        CREATE TABLE IF NOT EXISTS earnings_reactions (
            code TEXT NOT NULL,
            event_date TEXT NOT NULL,
            next_open_return REAL,
            next_close_return REAL,
            next_high_return REAL,
            next_low_return REAL,
            source TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(code, event_date)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_date TEXT NOT NULL,
            event_date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            score INTEGER NOT NULL,
            action TEXT NOT NULL,
            confidence TEXT,
            announcement_time TEXT,
            thesis TEXT,
            positive_factors_json TEXT,
            risk_factors_json TEXT,
            expected_reaction TEXT,
            evaluation_rule TEXT,
            missing_data_json TEXT,
            score_details_json TEXT,
            model_version TEXT,
            rules_version TEXT,
            llm_output_json TEXT,
            outcome_evaluated INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(recommendation_date, code)
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL UNIQUE,
            code TEXT NOT NULL,
            event_date TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            event_close REAL,
            next_open REAL,
            next_high REAL,
            next_low REAL,
            next_close REAL,
            next_open_return REAL,
            next_high_return REAL,
            next_low_return REAL,
            next_close_return REAL,
            max_drawdown REAL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(recommendation_id) REFERENCES recommendations(id)
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_id INTEGER,
            lesson_date TEXT NOT NULL,
            code TEXT,
            lesson_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(outcome_id) REFERENCES outcomes(id)
        );

        CREATE TABLE IF NOT EXISTS weekly_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            review_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS llm_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            model TEXT,
            prompt TEXT NOT NULL,
            input_json TEXT NOT NULL,
            output_json TEXT,
            status TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def upsert_earnings_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO earnings_events(date, code, name, announcement_time, fiscal_quarter, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, code) DO UPDATE SET
            name=excluded.name,
            announcement_time=excluded.announcement_time,
            fiscal_quarter=excluded.fiscal_quarter,
            source=excluded.source
        """,
        (
            event["date"],
            event["code"],
            event.get("name", ""),
            event.get("announcement_time", ""),
            event.get("fiscal_quarter", ""),
            event.get("source", ""),
            now_iso(),
        ),
    )


def upsert_daily_prices(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO daily_prices(code, date, open, high, low, close, volume, turnover_value, source, created_at)
        VALUES (:code, :date, :open, :high, :low, :close, :volume, :turnover_value, :source, :created_at)
        ON CONFLICT(code, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            turnover_value=excluded.turnover_value,
            source=excluded.source
        """,
        [{**row, "created_at": now_iso()} for row in rows],
    )


def upsert_financial_features(
    conn: sqlite3.Connection,
    code: str,
    as_of_date: str,
    features: dict[str, Any],
    missing_data: list[str],
    source: str,
) -> None:
    conn.execute(
        """
        INSERT INTO financial_features(code, as_of_date, features_json, missing_data_json, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, as_of_date) DO UPDATE SET
            features_json=excluded.features_json,
            missing_data_json=excluded.missing_data_json,
            source=excluded.source
        """,
        (code, as_of_date, to_json(features), to_json(missing_data), source, now_iso()),
    )


def upsert_earnings_reactions(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO earnings_reactions(
            code, event_date, next_open_return, next_close_return, next_high_return, next_low_return, source, created_at
        )
        VALUES (:code, :event_date, :next_open_return, :next_close_return, :next_high_return, :next_low_return, :source, :created_at)
        ON CONFLICT(code, event_date) DO UPDATE SET
            next_open_return=excluded.next_open_return,
            next_close_return=excluded.next_close_return,
            next_high_return=excluded.next_high_return,
            next_low_return=excluded.next_low_return,
            source=excluded.source
        """,
        [{**row, "created_at": now_iso()} for row in rows],
    )


def insert_recommendation(
    conn: sqlite3.Connection,
    recommendation_date: str,
    event_date: str,
    rec: dict[str, Any],
    score_details: dict[str, Any],
    model_version: str,
    rules_version: str,
    llm_output: dict[str, Any],
) -> int:
    conn.execute(
        """
        INSERT INTO recommendations(
            recommendation_date, event_date, code, name, score, action, confidence, announcement_time, thesis,
            positive_factors_json, risk_factors_json, expected_reaction, evaluation_rule, missing_data_json,
            score_details_json, model_version, rules_version, llm_output_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(recommendation_date, code) DO UPDATE SET
            score=excluded.score,
            action=excluded.action,
            confidence=excluded.confidence,
            announcement_time=excluded.announcement_time,
            thesis=excluded.thesis,
            positive_factors_json=excluded.positive_factors_json,
            risk_factors_json=excluded.risk_factors_json,
            expected_reaction=excluded.expected_reaction,
            evaluation_rule=excluded.evaluation_rule,
            missing_data_json=excluded.missing_data_json,
            score_details_json=excluded.score_details_json,
            model_version=excluded.model_version,
            rules_version=excluded.rules_version,
            llm_output_json=excluded.llm_output_json,
            outcome_evaluated=0
        """,
        (
            recommendation_date,
            event_date,
            rec["code"],
            rec.get("name", ""),
            int(rec.get("score", 0)),
            rec.get("action", "watch"),
            rec.get("confidence", ""),
            rec.get("announcement_time", ""),
            rec.get("thesis", ""),
            to_json(rec.get("positive_factors", [])),
            to_json(rec.get("risk_factors", [])),
            rec.get("expected_reaction", ""),
            rec.get("evaluation_rule", ""),
            to_json(rec.get("missing_data", [])),
            to_json(score_details),
            model_version,
            rules_version,
            to_json(llm_output),
            now_iso(),
        ),
    )
    row = conn.execute(
        "SELECT id FROM recommendations WHERE recommendation_date = ? AND code = ?",
        (recommendation_date, rec["code"]),
    ).fetchone()
    return int(row["id"])


def insert_llm_run(
    conn: sqlite3.Connection,
    run_type: str,
    model: str,
    prompt: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None,
    status: str,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO llm_runs(run_type, model, prompt, input_json, output_json, status, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_type, model, prompt, to_json(input_data), to_json(output_data), status, error, now_iso()),
    )


def fetch_unevaluated_recommendations(conn: sqlite3.Connection, before_date: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM recommendations
            WHERE outcome_evaluated = 0 AND event_date < ?
            ORDER BY event_date ASC, score DESC
            """,
            (before_date,),
        ).fetchall()
    )


def insert_outcome(conn: sqlite3.Connection, outcome: dict[str, Any]) -> int:
    conn.execute(
        """
        INSERT INTO outcomes(
            recommendation_id, code, event_date, evaluation_date, event_close, next_open, next_high,
            next_low, next_close, next_open_return, next_high_return, next_low_return, next_close_return,
            max_drawdown, result, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(recommendation_id) DO UPDATE SET
            evaluation_date=excluded.evaluation_date,
            event_close=excluded.event_close,
            next_open=excluded.next_open,
            next_high=excluded.next_high,
            next_low=excluded.next_low,
            next_close=excluded.next_close,
            next_open_return=excluded.next_open_return,
            next_high_return=excluded.next_high_return,
            next_low_return=excluded.next_low_return,
            next_close_return=excluded.next_close_return,
            max_drawdown=excluded.max_drawdown,
            result=excluded.result
        """,
        (
            outcome["recommendation_id"],
            outcome["code"],
            outcome["event_date"],
            outcome["evaluation_date"],
            outcome["event_close"],
            outcome["next_open"],
            outcome["next_high"],
            outcome["next_low"],
            outcome["next_close"],
            outcome["next_open_return"],
            outcome["next_high_return"],
            outcome["next_low_return"],
            outcome["next_close_return"],
            outcome["max_drawdown"],
            outcome["result"],
            now_iso(),
        ),
    )
    conn.execute("UPDATE recommendations SET outcome_evaluated = 1 WHERE id = ?", (outcome["recommendation_id"],))
    row = conn.execute(
        "SELECT id FROM outcomes WHERE recommendation_id = ?",
        (outcome["recommendation_id"],),
    ).fetchone()
    return int(row["id"])


def insert_lesson(conn: sqlite3.Connection, outcome_id: int | None, lesson_date: str, code: str | None, lesson: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO lessons(outcome_id, lesson_date, code, lesson_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (outcome_id, lesson_date, code, to_json(lesson), now_iso()),
    )


def fetch_outcomes_between(conn: sqlite3.Connection, start: str, end: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM outcomes WHERE evaluation_date BETWEEN ? AND ? ORDER BY evaluation_date, code",
            (start, end),
        ).fetchall()
    )


def insert_weekly_review(conn: sqlite3.Connection, week_start: str, week_end: str, review: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO weekly_reviews(week_start, week_end, review_json, created_at) VALUES (?, ?, ?, ?)",
        (week_start, week_end, to_json(review), now_iso()),
    )

