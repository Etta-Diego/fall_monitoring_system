"""Read-only data access for the Streamlit dashboard (kept out of app/ so it can be unit tested)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from fallmon.config import Config
from fallmon.guards import TestLockError, check_frozen

SUMMARY_PATH = Path("results/SUMMARY.md")
LOG_TABLES = {"Activity log": "activity_log", "Unknown activity log": "unknown_activity_log", "Alert log": "alert_log"}
# feature -> (rule, verifier-params key, comparison)
RULE_OF_FEATURE = {
    "impact_peak_g": ("R_impact", "impact_g", ">="),
    "orientation_change_deg": ("R_orient", "orient_deg", ">="),
    "post_am_std_g": ("R_still", "still_std_g", "<="),
    "low_activity_s": ("R_rest", "rest_s", ">="),
}


def test_unlocked(cfg: Config) -> bool:
    """Test trials may be replayed only after the final evaluation (frozen config valid + SUMMARY.md)."""
    if not SUMMARY_PATH.exists():
        return False
    try:
        check_frozen(cfg)
    except (TestLockError, FileNotFoundError):
        return False
    return True


def replayable_trials(index: pd.DataFrame, splits: dict, unlocked: bool) -> pd.DataFrame:
    """Trials the Live Replay page may offer.

    Before the test split is unlocked: train and validation subjects, known ADLs and falls only.
    Unknown ADLs stay hidden so nobody can tune by eye on them (PRD 7.2).
    """
    if unlocked:
        return index
    return index[index["subject_id"].isin(splits["train"] + splits["val"])
                 & index["activity_group"].isin(["known_adl", "fall"])]


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def list_runs(db_path: Path) -> pd.DataFrame:
    if not Path(db_path).exists():
        return pd.DataFrame(columns=["run_id", "created_at", "mode", "split", "frozen_hash"])
    with _connect(db_path) as con:
        return pd.read_sql("SELECT run_id, created_at, mode, split, frozen_hash FROM runs ORDER BY created_at DESC, "
                           "run_id DESC", con)


def run_params(db_path: Path, run_id: str) -> dict | None:
    with _connect(db_path) as con:
        row = con.execute("SELECT config_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row[0]).get("verifier_params") if row else None


def events(db_path: Path, run_ids: list[str]) -> pd.DataFrame:
    if not run_ids:
        return pd.DataFrame()
    q = f"SELECT * FROM events WHERE run_id IN ({','.join('?' * len(run_ids))}) ORDER BY run_id, trial_id, t_open_s"
    with _connect(db_path) as con:
        return pd.read_sql(q, con, params=run_ids)


def log_table(db_path: Path, table: str, run_ids: list[str], modes: list[str] | None = None,
              subjects: list[str] | None = None, limit: int = 5000) -> pd.DataFrame:
    """Rows of one log table, filtered by run, mode and subject. Mode comes from the runs table."""
    if table not in LOG_TABLES.values() or not run_ids:
        return pd.DataFrame()
    where = [f"t.run_id IN ({','.join('?' * len(run_ids))})"]
    params: list = list(run_ids)
    if modes:
        where.append(f"r.mode IN ({','.join('?' * len(modes))})")
        params += modes
    if subjects:
        where.append(f"t.subject_id IN ({','.join('?' * len(subjects))})")
        params += subjects
    q = (f"SELECT t.*, r.mode AS run_mode FROM {table} t JOIN runs r ON r.run_id = t.run_id "
         f"WHERE {' AND '.join(where)} ORDER BY t.id LIMIT {int(limit)}")
    with _connect(db_path) as con:
        df = pd.read_sql(q, con, params=params)
    df = df.drop(columns="mode", errors="ignore").rename(columns={"run_mode": "mode"})  # alert_log has its own copy
    return df[["mode"] + [c for c in df.columns if c != "mode"]]


def rule_table(event_row: pd.Series, params: dict | None) -> pd.DataFrame:
    """One row per verifier feature: value, the rule it feeds, threshold, pass/fail."""
    if not isinstance(event_row.get("features_json"), str):
        return pd.DataFrame()
    feats = json.loads(event_row["features_json"])
    rules = json.loads(event_row["rules_json"]) if isinstance(event_row.get("rules_json"), str) else {}
    rows = []
    for name, value in feats.items():
        rule, key, op = RULE_OF_FEATURE.get(name, ("", None, ""))
        thr = params.get(key) if params and key else None
        rows.append({"feature": name, "value": value, "rule": rule,
                     "threshold": f"{op} {thr:g}" if thr is not None else "",
                     "pass": ("PASS" if rules.get(rule) else "FAIL") if rule else "(reported only)"})
    return pd.DataFrame(rows)


def results_files(results_dir: Path = Path("results")) -> tuple[list[Path], list[Path]]:
    """Markdown tables and PNG figures under results/ (read-only)."""
    tables = sorted(p for p in (results_dir / "tables").rglob("*.md"))
    figures = sorted(p for p in (results_dir / "figures").rglob("*.png"))
    summary = [results_dir / "SUMMARY.md"] if (results_dir / "SUMMARY.md").exists() else []
    return summary + tables, figures
