import math

import numpy as np

from fallmon.preprocessing import preprocess
from fallmon.verifier import VerifierParams, apply_rules, compute_features, localise_impact, verify
from synthetic import fall_signal, hard_sit_signal, standing


def _verify(cfg, data, t_event, **overrides):
    phys = preprocess(data, cfg)
    p = VerifierParams.from_config(cfg)
    p = VerifierParams(**{**p.__dict__, **overrides})
    i = localise_impact(phys, t_event, cfg)
    return verify(phys, i, p, cfg, truncated=False)


def test_fall_shaped_signal_verifies(cfg):
    r = _verify(cfg, fall_signal(), t_event=6.5)
    assert r.verified, r.reason
    assert abs(r.t_impact - 6.4) < 0.1
    assert r.features["orientation_change_deg"] > 80
    assert r.features["low_activity_s"] >= 0.9
    assert r.reason.endswith("-> VERIFIED")


def test_hard_sit_down_then_walk_rejects(cfg):
    r = _verify(cfg, hard_sit_signal(), t_event=6.5)
    assert r.rules["R_impact"]  # the impact alone looks like a fall...
    assert not r.verified, r.reason  # ...but orientation, stillness and rest do not
    assert r.features["orientation_change_deg"] < 30
    assert r.reason.endswith("-> REJECTED")


def test_weak_impact_rejects_even_if_still(cfg):
    d = fall_signal()
    i = int(6.4 * 200)
    d[i:i + 12, 0], d[i:i + 12, 2] = 1.0, 0.5  # soften impact to ~1.1 g
    r = _verify(cfg, d, t_event=6.5)
    assert not r.rules["R_impact"] and not r.verified


def test_localise_impact_picks_max_in_search_window(cfg):
    d = standing(10.0)
    d[int(4.0 * 200):int(4.0 * 200) + 12, 2] = 2.0
    d[int(6.0 * 200):int(6.0 * 200) + 12, 2] = 3.5
    phys = preprocess(d, cfg)
    assert abs(localise_impact(phys, 5.5, cfg) / 50 - 6.0) < 0.1  # window [4.0, 6.5] holds both; 6.0 is larger
    assert abs(localise_impact(phys, 3.5, cfg) / 50 - 4.0) < 0.1  # window [2.0, 4.5]


def test_features_nan_without_post_data(cfg):
    phys = preprocess(fall_signal(seconds=6.5), cfg)  # ends 0.1 s after impact
    i = localise_impact(phys, 6.4, cfg)
    feats, flags = compute_features(phys, i, 2.0, cfg)
    assert math.isnan(feats["orientation_change_deg"]) and math.isnan(feats["low_activity_s"])
    p = VerifierParams.from_config(cfg)
    verified, rules = apply_rules(feats, p)
    assert rules["R_impact"] and not rules["R_orient"] and not rules["R_rest"] and not verified
    assert flags["post_samples"] == 0


def test_combine_modes(cfg):
    base = VerifierParams.from_config(cfg)
    feats = {"impact_peak_g": 3.0, "gyro_peak_dps": 0, "orientation_change_deg": 60.0, "post_am_std_g": 0.5,
             "post_gm_mean_dps": 0, "low_activity_s": 0.0}  # impact + orientation only
    mk = lambda **kw: VerifierParams(**{**base.__dict__, **kw})
    assert apply_rules(feats, mk(combine="impact_and_any"))[0]
    assert not apply_rules(feats, mk(combine="impact_and_k_of_3", k=2))[0]
    assert not apply_rules(feats, mk(combine="all"))[0]
    feats["low_activity_s"] = 2.0
    assert apply_rules(feats, mk(combine="impact_and_k_of_3", k=2))[0]


def test_params_roundtrip(tmp_path, cfg):
    p = VerifierParams.from_config(cfg)
    p.save(tmp_path / "v.json", {"note": "x"})
    assert VerifierParams.load(tmp_path / "v.json") == p
