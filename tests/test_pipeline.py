import sqlite3

import numpy as np
import torch

from fallmon.data_loader import Trial
from fallmon.dte import CNN1D, DeepTimeEnsemble
from fallmon.pipeline import ALERT, COOLDOWN, HOLD, KNOWN, REJECTED, StreamProcessor, run_batch
from fallmon.preprocessing import Scaler, preprocess
from fallmon.storage import Storage
from fallmon.stream_simulator import StreamSimulator

CHANNELS = ["ax", "ay", "az", "gx", "gy", "gz", "Am", "Gm"]


def _identity_scaler():
    return Scaler(CHANNELS, np.zeros(8), np.ones(8), ["SA01"])


class SpikeEnsemble:
    """Stub: unsure (OOD) whenever Am in the last 1 s exceeds 2 g, confident otherwise."""

    window_samples = [50, 100, 150]
    classes = ["static", "walking"]

    def predict_steps(self, x, ends):
        p = np.array([[0.5, 0.5] if x[e - 50:e, 6].max() > 2.0 else [0.99, 0.01] for e in ends])
        return p, np.stack([p] * 3)


def _trial(spikes_s=(), seconds=15.0, trial_id="F01_SA01_R01"):
    n = int(seconds * 200)
    data = np.zeros((n, 6))
    data[:, 2] = 1.0  # standing still, 1 g on z
    for s in spikes_s:
        i = int(s * 200)
        data[i:i + 20, 2] = 4.0  # 0.1 s, 4 g impact
    return Trial(trial_id, "SA01", "young", trial_id[:3], "fall", 1, 200, data)


def _run(cfg, trials, storage=None, ens=None, mode="baseline", params=None):
    proc = StreamProcessor(mode, cfg, ens or SpikeEnsemble(), _identity_scaler(), storage, None, "test-run",
                           params=params)
    return run_batch(trials, proc)


def test_no_event_when_always_confident(cfg):
    d = _run(cfg, [_trial()])
    assert (d["status"] == KNOWN).all() and not d["new_alert"].any()
    assert d["t_s"].iloc[0] == 3.0 and np.allclose(np.diff(d["t_s"]), 0.5)


def test_baseline_alerts_once_per_event(cfg):
    d = _run(cfg, [_trial(spikes_s=[6.0])])
    assert d["new_alert"].sum() == 1
    first = d[d["new_alert"]].iloc[0]
    assert first["status"] == ALERT and 6.0 <= first["t_s"] <= 7.0
    assert d.loc[d["is_ood"], "event_id"].nunique() == 1


def test_cooldown_blocks_second_alert_then_allows_after(cfg):
    d = _run(cfg, [_trial(spikes_s=[5.0, 9.0, 17.0], seconds=20.0)])  # cooldown 10 s after the alert at ~5 s
    assert d["new_alert"].sum() == 2
    assert (d["status"] == COOLDOWN).any()
    alert_times = d.loc[d["new_alert"], "t_s"].tolist()
    assert alert_times[1] - alert_times[0] >= cfg.events.cooldown_s


def test_state_resets_at_trial_boundary(cfg):
    # Spike near the end of trial 1; trial 2 starts with a spike: cooldown must not carry over.
    d = _run(cfg, [_trial(spikes_s=[13.0], trial_id="F01_SA01_R01"), _trial(spikes_s=[3.2], trial_id="F01_SA01_R02")])
    per_trial = d.groupby("trial_id")["new_alert"].sum()
    assert per_trial["F01_SA01_R01"] == 1 and per_trial["F01_SA01_R02"] == 1
    assert d[d.trial_id == "F01_SA01_R02"]["t_s"].iloc[0] == 3.0  # buffers restarted


def test_stream_confidence_matches_offline_inference(cfg):
    torch.manual_seed(0)
    ens = DeepTimeEnsemble([CNN1D(8, 3, 0.3) for _ in range(3)], [50, 100, 150], ["a", "b", "c"])
    rng = np.random.default_rng(0)
    trial = _trial(seconds=8.0)
    trial = Trial(trial.trial_id, "SA01", "young", "F01", "fall", 1, 200, trial.data + 0.2 * rng.standard_normal(trial.data.shape))
    d = _run(cfg, [trial], ens=ens)
    x = preprocess(trial.data, cfg)
    ends = np.arange(150, len(x) + 1, 25)
    p, _ = ens.predict_steps(x, ends)
    np.testing.assert_allclose(d["confidence"].to_numpy(), p.max(axis=1), atol=1e-5)


def test_storage_rows(cfg, tmp_path):
    storage = Storage(tmp_path / "t.db")
    _run(cfg, [_trial(spikes_s=[6.0])], storage=storage)
    storage.close()
    con = sqlite3.connect(tmp_path / "t.db")
    status, reason, t_close = con.execute("SELECT status, reason, t_close_s FROM events").fetchone()
    assert status == ALERT and "baseline" in reason and t_close is not None
    (channel, message), = con.execute("SELECT channel, message FROM alert_log").fetchall()
    assert message.startswith("[SIMULATED]") and "simulated IoT stream" in message
    assert con.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0] > 0


def test_simulator_emits_all_samples_in_order():
    t1, t2 = _trial(seconds=1.0), _trial(seconds=0.5, trial_id="D01_SA01_R01")
    samples = list(StreamSimulator([t1, t2], realtime=False))
    assert len(samples) == 300
    assert [s.t_s for s in samples[:3]] == [0.0, 0.005, 0.01]
    assert samples[200].trial_id == "D01_SA01_R01" and samples[200].t_s == 0.0


# ----- proposed mode (Phase 4) ------------------------------------------------------------------

from fallmon.tune_verifier import TrialSteps, _FeatureCache, replay  # noqa: E402
from fallmon.verifier import VerifierParams  # noqa: E402
from synthetic import as_trial, fall_signal, hard_sit_signal  # noqa: E402


def _params(cfg, **kw):
    p = VerifierParams.from_config(cfg)
    return VerifierParams(**{**p.__dict__, **kw})


def test_proposed_holds_then_alerts_on_fall(cfg, tmp_path):
    storage = Storage(tmp_path / "p.db")
    d = _run(cfg, [as_trial(fall_signal(), "F01_SA01_R01")], storage=storage, mode="proposed", params=_params(cfg))
    storage.close()
    assert d["new_alert"].sum() == 1
    first_ood = d[d["is_ood"]].iloc[0]
    alert = d[d["new_alert"]].iloc[0]
    assert first_ood["status"] == HOLD and not first_ood["new_alert"]
    assert alert["t_s"] - first_ood["t_s"] >= 1.5  # waited for the post-impact window
    con = sqlite3.connect(tmp_path / "p.db")
    status, reason, delay, t_imp = con.execute("SELECT status, reason, decision_delay_s, t_impact_s FROM events").fetchone()
    assert status == ALERT and reason.endswith("VERIFIED") and delay > 1.5 and abs(t_imp - 6.4) < 0.1
    (msg,), = con.execute("SELECT message FROM alert_log").fetchall()
    assert msg.startswith("[SIMULATED] Verified fall alert")
    assert con.execute("SELECT COUNT(*) FROM unknown_activity_log").fetchone()[0] == 0


def test_proposed_rejects_hard_sit_and_logs_unknown(cfg, tmp_path):
    storage = Storage(tmp_path / "r.db")
    d = _run(cfg, [as_trial(hard_sit_signal(), "D07_SA01_R01", "known_adl")], storage=storage, mode="proposed",
             params=_params(cfg))
    storage.close()
    assert d["new_alert"].sum() == 0 and (d["status"] == REJECTED).any()
    con = sqlite3.connect(tmp_path / "r.db")
    assert con.execute("SELECT status FROM events").fetchone()[0] == REJECTED
    assert con.execute("SELECT COUNT(*) FROM unknown_activity_log").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0] == 0


def _early_event_then_fall():
    """A 2.2 g bump at 4.0 s opens an event that merges into a real fall impact at 5.6 s."""
    d = fall_signal(seconds=15.0, t_impact=5.6)
    i = int(4.0 * 200)
    d[i:i + 12, 2] = 2.2
    return d


def test_rearm_after_reject_catches_fall_inside_early_event(cfg):
    trial = as_trial(_early_event_then_fall(), "F01_SA01_R03")
    no_rearm = _run(cfg, [trial], mode="proposed", params=_params(cfg, rearm_after_reject=False))
    rearm = _run(cfg, [trial], mode="proposed", params=_params(cfg, rearm_after_reject=True))
    assert no_rearm["new_alert"].sum() == 0  # verifier looked at the 4.0 s bump only
    assert rearm["new_alert"].sum() == 1
    assert (rearm["status"] == REJECTED).any()


def test_truncated_verification_at_trial_end(cfg):
    d = _run(cfg, [as_trial(fall_signal(seconds=14.6, t_impact=13.5), "F01_SA01_R04")], mode="proposed",
             params=_params(cfg))
    end_rows = d[d["predicted_activity"] == ""]
    assert len(end_rows) == 1 and end_rows.iloc[0]["status"] in (ALERT, REJECTED)


def test_tuning_replay_matches_stream_processor(cfg):
    trials = [as_trial(fall_signal(), "F01_SA01_R01"), as_trial(hard_sit_signal(), "D07_SA01_R01", "known_adl"),
              as_trial(_early_event_then_fall(), "F01_SA01_R03")]
    for rearm in (False, True):
        p = _params(cfg, rearm_after_reject=rearm)
        stream = _run(cfg, trials, mode="proposed", params=p)
        steps = []
        for tr in trials:
            phys = preprocess(tr.data, cfg)
            ends = np.arange(150, len(phys) + 1, 25)
            conf = SpikeEnsemble().predict_steps(phys, ends)[0].max(axis=1)
            steps.append(TrialSteps(tr.trial_id, "SA01", tr.activity_group, tr.activity_code, phys, ends, conf, 0.0))
        per_trial, _ = replay(steps, "proposed", p, cfg, cfg.ood.threshold, _FeatureCache(cfg))
        stream_alerts = stream.groupby("trial_id")["new_alert"].sum()
        for row in per_trial.itertuples():
            assert row.alerts == stream_alerts[row.trial_id], (rearm, row.trial_id)
