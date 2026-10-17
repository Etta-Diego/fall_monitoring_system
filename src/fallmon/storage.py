"""SQLite logging: runs, activity log, events (decision trace), unknown-activity log, alert log (PRD 12.3)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, created_at TEXT, mode TEXT, split TEXT, frozen_hash TEXT, config_json TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY, run_id TEXT, t_s REAL, subject_id TEXT, trial_id TEXT, activity TEXT, confidence REAL
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, run_id TEXT, mode TEXT, subject_id TEXT, trial_id TEXT,
    t_open_s REAL, t_impact_s REAL, t_decision_s REAL, t_close_s REAL, min_confidence REAL,
    status TEXT, reason TEXT, features_json TEXT, rules_json TEXT, truncated INTEGER,
    decision_delay_s REAL, latency_ms REAL
);
CREATE TABLE IF NOT EXISTS unknown_activity_log (
    id INTEGER PRIMARY KEY, run_id TEXT, event_id TEXT, t_s REAL, subject_id TEXT, trial_id TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY, run_id TEXT, event_id TEXT, t_s REAL, subject_id TEXT, trial_id TEXT,
    mode TEXT, channel TEXT, delivered INTEGER, message TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_activity_run ON activity_log(run_id);
"""


def new_run_id(mode: str) -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{mode}-{uuid.uuid4().hex[:6]}"


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)

    def start_run(self, mode: str, split: str, config: dict, frozen_hash: str | None = None) -> str:
        run_id = new_run_id(mode)
        self.conn.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), mode, split, frozen_hash,
             json.dumps(config, default=str)),
        )
        self.conn.commit()
        return run_id

    def log_activity(self, run_id: str, t_s: float, subject_id: str, trial_id: str, activity: str,
                     confidence: float) -> None:
        self.conn.execute(
            "INSERT INTO activity_log (run_id, t_s, subject_id, trial_id, activity, confidence) VALUES (?,?,?,?,?,?)",
            (run_id, t_s, subject_id, trial_id, activity, confidence),
        )

    def write_event(self, row: dict) -> None:
        """Insert or replace an event row (called again when the event's state changes)."""
        cols = ("event_id", "run_id", "mode", "subject_id", "trial_id", "t_open_s", "t_impact_s", "t_decision_s",
                "t_close_s", "min_confidence", "status", "reason", "features_json", "rules_json", "truncated",
                "decision_delay_s", "latency_ms")
        self.conn.execute(
            f"INSERT OR REPLACE INTO events ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            tuple(row.get(c) for c in cols),
        )

    def log_unknown(self, run_id: str, event_id: str, t_s: float, subject_id: str, trial_id: str, reason: str) -> None:
        self.conn.execute(
            "INSERT INTO unknown_activity_log (run_id, event_id, t_s, subject_id, trial_id, reason) VALUES (?,?,?,?,?,?)",
            (run_id, event_id, t_s, subject_id, trial_id, reason),
        )

    def log_alert(self, run_id: str, event_id: str, t_s: float, subject_id: str, trial_id: str, mode: str,
                  channel: str, delivered: bool, message: str) -> None:
        self.conn.execute(
            "INSERT INTO alert_log (run_id, event_id, t_s, subject_id, trial_id, mode, channel, delivered, message) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, event_id, t_s, subject_id, trial_id, mode, channel, int(delivered), message),
        )

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
