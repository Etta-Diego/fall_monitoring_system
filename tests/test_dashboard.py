from pathlib import Path

import pandas as pd
import pytest
import yaml

from fallmon import dashboard_data as dd
from fallmon.config import DEFAULT_CONFIG_PATH
from fallmon.pipeline import StreamProcessor, run_batch, run_config
from fallmon.storage import Storage
from fallmon.verifier import VerifierParams
from synthetic import as_trial, fall_signal, hard_sit_signal
from test_pipeline import SpikeEnsemble, _identity_scaler

SPLITS = {"train": ["SA01"], "val": ["SA02"], "test": ["SE06"]}


def test_replayable_trials_hide_test_and_unknown_until_unlocked():
    index = pd.DataFrame({"trial_id": ["a", "b", "c", "d"], "subject_id": ["SA01", "SA02", "SA02", "SE06"],
                          "activity_group": ["fall", "known_adl", "unknown_adl", "fall"]})
    locked = dd.replayable_trials(index, SPLITS, unlocked=False)
    assert list(locked["trial_id"]) == ["a", "b"]
    assert len(dd.replayable_trials(index, SPLITS, unlocked=True)) == 4


@pytest.fixture
def logged_db(tmp_path, cfg):
    db = tmp_path / "d.db"
    storage = Storage(db)
    params = VerifierParams.from_config(cfg)
    runs = {}
    for mode in ("baseline", "proposed"):
        run_id = storage.start_run(mode, "val", run_config(cfg, params))
        proc = StreamProcessor(mode, cfg, SpikeEnsemble(), _identity_scaler(), storage, None, run_id, params=params)
        run_batch([as_trial(fall_signal(), "F01_SA01_R01"), as_trial(hard_sit_signal(), "D07_SA02_R01", "known_adl")],
                  proc)
        runs[mode] = run_id
    storage.close()
    return db, runs


def test_runs_events_and_rule_table(logged_db):
    db, runs = logged_db
    assert set(dd.list_runs(db)["run_id"]) == set(runs.values())
    ev = dd.events(db, [runs["proposed"]])
    assert set(ev["status"]) == {"ALERT", "REJECTED"}
    params = dd.run_params(db, runs["proposed"])
    rejected = ev[ev["status"] == "REJECTED"].iloc[0]
    rules = dd.rule_table(rejected, params).set_index("feature")
    assert rules.loc["impact_peak_g", "pass"] == "PASS" and rules.loc["impact_peak_g", "threshold"] == f">= {params['impact_g']:g}"
    assert rules.loc["gyro_peak_dps", "pass"] == "(reported only)"
    baseline_event = dd.events(db, [runs["baseline"]]).iloc[0]
    assert dd.rule_table(baseline_event, None).empty  # baseline events have no verifier features


def test_log_table_filters(logged_db):
    db, runs = logged_db
    both = list(runs.values())
    unknown = dd.log_table(db, "unknown_activity_log", both)
    assert len(unknown) == 1 and unknown.iloc[0]["mode"] == "proposed"
    alerts = dd.log_table(db, "alert_log", both, modes=["baseline"])
    assert len(alerts) > 0 and set(alerts["mode"]) == {"baseline"}
    assert dd.log_table(db, "alert_log", both, subjects=["SA99"]).empty
    assert dd.log_table(db, "events; DROP TABLE runs", both).empty  # only whitelisted tables


@pytest.mark.skipif(not Path("models/verifier_config.json").exists() or not Path("data/processed/index.parquet").exists(),
                    reason="needs trained models and the dataset index")
def test_dashboard_app_side_by_side_replay(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
    raw["logging"]["db_path"] = str(tmp_path / "dash.db")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw))
    monkeypatch.setenv("FALLMON_CONFIG", str(cfg_path))

    at = AppTest.from_file(str(Path("app/dashboard.py").resolve()), default_timeout=120).run()
    assert not at.exception
    assert "simulated IoT stream" in at.warning[0].value
    for page in ("Event Details", "Logs", "Results"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
    at.sidebar.radio[0].set_value("Live Replay").run()
    splits = yaml.safe_load(Path("data/splits.json").read_text())
    at.selectbox[0].set_value(splits["val"][0]).run()
    assert at.selectbox[0].value in splits["val"]  # validation subject offered; test subjects are not
    assert not set(at.selectbox[0].options) & set(splits["test"])
    at.radio[0].set_value("side by side")
    at.slider[0].set_value(100)
    at.button[0].click().run()
    assert not at.exception
    assert any("Replay finished" in s.value for s in at.success)
    assert dd.list_runs(tmp_path / "dash.db")["mode"].tolist().count("proposed") == 1
