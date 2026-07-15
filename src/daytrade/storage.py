from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True); conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row; init_db(conn); return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS daytrade_runs (
      trade_date TEXT PRIMARY KEY, status TEXT NOT NULL, universe_count INTEGER NOT NULL,
      candidate_count INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS daytrade_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL, rank INTEGER NOT NULL,
      code TEXT NOT NULL, name TEXT NOT NULL, score INTEGER NOT NULL, theme TEXT,
      features_json TEXT NOT NULL, components_json TEXT NOT NULL, news_json TEXT NOT NULL,
      comment_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(trade_date, code)
    );
    CREATE TABLE IF NOT EXISTS daytrade_outcomes (
      id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL UNIQUE, trade_date TEXT NOT NULL,
      code TEXT NOT NULL, reference_price REAL, high REAL, low REAL, close REAL,
      max_up REAL, max_down REAL, close_return REAL, target_hit INTEGER NOT NULL,
      stop_hit INTEGER NOT NULL, analysis_json TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(candidate_id) REFERENCES daytrade_candidates(id)
    );
    CREATE TABLE IF NOT EXISTS daytrade_learning_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, trained_at TEXT NOT NULL, sample_count INTEGER NOT NULL,
      status TEXT NOT NULL, profile_json TEXT NOT NULL
    );
    """); conn.commit()


def save_run(conn: sqlite3.Connection, trade_date: str, universe_count: int, candidates: list[dict[str, Any]], payload: dict[str, Any], status: str = "ranked") -> None:
    now = _now(); conn.execute("INSERT OR REPLACE INTO daytrade_runs VALUES (?, ?, ?, ?, ?, ?)", (trade_date, status, universe_count, len(candidates), _json(payload), now))
    conn.execute("DELETE FROM daytrade_candidates WHERE trade_date=? AND id NOT IN (SELECT candidate_id FROM daytrade_outcomes)", (trade_date,))
    for rank, row in enumerate(candidates, 1):
        conn.execute("""INSERT INTO daytrade_candidates(trade_date,rank,code,name,score,theme,features_json,components_json,news_json,comment_json,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(trade_date,code) DO UPDATE SET rank=excluded.rank,name=excluded.name,score=excluded.score,
          theme=excluded.theme,features_json=excluded.features_json,components_json=excluded.components_json,news_json=excluded.news_json,comment_json=excluded.comment_json""", (trade_date, rank, row["code"], row.get("name", ""), row["score"], ",".join(row.get("themes") or ["その他"]), _json(row["features"]), _json(row["components"]), _json(row.get("news") or []), _json(row["comment"]), now))
    conn.commit()


def notification_sent(conn: sqlite3.Connection, trade_date: str) -> bool:
    row = conn.execute("SELECT status FROM daytrade_runs WHERE trade_date=?", (trade_date,)).fetchone()
    return bool(row and row["status"] == "sent")


def pending_candidates(conn: sqlite3.Connection, trade_date: str) -> list[sqlite3.Row]:
    return list(conn.execute("""SELECT c.* FROM daytrade_candidates c LEFT JOIN daytrade_outcomes o ON o.candidate_id=c.id
      WHERE c.trade_date=? AND o.id IS NULL ORDER BY c.rank""", (trade_date,)).fetchall())


def save_outcome(conn: sqlite3.Connection, row: sqlite3.Row, outcome: dict[str, Any]) -> None:
    conn.execute("""INSERT OR REPLACE INTO daytrade_outcomes(candidate_id,trade_date,code,reference_price,high,low,close,max_up,max_down,close_return,target_hit,stop_hit,analysis_json,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (row["id"], row["trade_date"], row["code"], outcome.get("reference_price"), outcome.get("high"), outcome.get("low"), outcome.get("close"), outcome.get("max_up"), outcome.get("max_down"), outcome.get("close_return"), int(outcome.get("target_hit", False)), int(outcome.get("stop_hit", False)), _json(outcome.get("analysis") or {}), _now()))


def recent_dashboard(conn: sqlite3.Connection, limit: int = 20) -> dict[str, Any]:
    candidates = [dict(row) for row in conn.execute("SELECT * FROM daytrade_candidates ORDER BY trade_date DESC, rank LIMIT ?", (limit,)).fetchall()]
    outcomes = [dict(row) for row in conn.execute("SELECT * FROM daytrade_outcomes ORDER BY trade_date DESC, id DESC LIMIT ?", (limit,)).fetchall()]
    for row in candidates:
        row["features"] = json.loads(row.pop("features_json")); row["components"] = json.loads(row.pop("components_json")); row["news"] = json.loads(row.pop("news_json")); row["comment"] = json.loads(row.pop("comment_json"))
    for row in outcomes: row["analysis"] = json.loads(row.pop("analysis_json"))
    total = len(outcomes); hits = sum(row["target_hit"] for row in outcomes)
    return {"candidates": candidates, "outcomes": outcomes, "summary": {"evaluated": total, "target_hits": hits, "hit_rate": hits / total if total else None}}


def _json(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True)
def _now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
