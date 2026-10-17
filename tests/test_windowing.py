import numpy as np
import pandas as pd
import pytest

from fallmon.guards import LeakageError, assert_no_unknown_in_training, assert_scaler_fit_on_train
from fallmon.preprocessing import Scaler
from fallmon.windowing import (STATIC_CLASS, ProcessedTrial, class_names, decision_step_ends, make_windows,
                               window_label, window_starts)

SPLITS = {"train": ["SA01", "SA02"], "val": ["SA03"], "test": ["SE06"]}


def _trial(code, subject="SA01", n=600, group="known_adl"):
    x = np.tile(np.arange(n, dtype=float)[:, None], (1, 8))  # value = sample index, so order is visible
    return ProcessedTrial(f"{code}_{subject}_R01", subject, "young", code, group, x)


def _identity_scaler():
    return Scaler(["ax", "ay", "az", "gx", "gy", "gz", "Am", "Gm"], np.zeros(8), np.ones(8), ["SA01"])


def test_window_starts_cap_and_bounds():
    s = window_starts(5000, 150, 12, cap=200)
    assert len(s) == 200 and s[0] == 0 and s[-1] == (5000 - 150) // 12 * 12
    assert len(window_starts(600, 150, 12, cap=200)) == (600 - 150) // 12 + 1
    assert len(window_starts(100, 150, 12, cap=200)) == 0


def test_windows_keep_temporal_order_and_labels(cfg):
    # _trial's ramp signal is far from still, so every window gets the activity's group.
    x, y, meta = make_windows([_trial("D07")], 50, _identity_scaler(), cfg)
    assert x.shape[1:] == (8, 50)
    np.testing.assert_array_equal(x[0, 0], np.arange(50))  # contiguous, not shuffled
    np.testing.assert_array_equal(x[1, 0], np.arange(12, 62))  # stride 12 samples
    assert set(y) == {class_names(cfg).index("sit_stand")}
    assert set(meta["label"]) == {"sit_stand"} and set(meta["activity_code"]) == {"D07"}


def _still(n=50, am=1.0):
    w = np.zeros((n, 8))
    w[:, 2] = w[:, 6] = am
    w[:, 7] = 3.0  # Gm 3 deg/s, typical at rest
    return w


def test_static_label_for_still_window_any_activity(cfg):
    for code in ("D07", "D15", "D17"):
        assert window_label(_still(), code, cfg) == STATIC_CLASS


def test_moving_window_gets_group_label(cfg):
    w = _still()
    w[:, 6] = 1.0 + 0.3 * np.sin(np.linspace(0, 6, 50))  # Am varies ~0.2 g std
    assert window_label(w, "D02", cfg) == "walking"
    assert window_label(w, "D15", cfg) == "bending"
    w2 = _still()
    w2[:, 7] = 40.0  # still Am but rotating
    assert window_label(w2, "D07", cfg) == "sit_stand"


def test_activity_scheme_keeps_codes(cfg):
    cfg_act = cfg.model_copy(update={"dte": cfg.dte.model_copy(update={"label_scheme": "activity"})})
    assert class_names(cfg_act) == list(cfg.activities.known_adls)
    assert window_label(_still(), "D07", cfg_act) == "D07"


def test_class_groups_cover_known_adls_only(cfg):
    grouped = sorted(c for codes in cfg.activities.class_groups.values() for c in codes)
    assert grouped == sorted(cfg.activities.known_adls)
    assert not set(grouped) & (set(cfg.activities.unknown_adls) | set(cfg.activities.falls))


def test_decision_steps_start_when_longest_window_full(cfg):
    ends = decision_step_ends(600, cfg)  # 12 s at 50 Hz
    assert ends[0] == 150  # 3 s
    assert np.all(np.diff(ends) == 25)  # 0.5 s
    assert ends[-1] <= 600


def test_guard2_rejects_fall_and_unknown_codes(cfg):
    known = list(cfg.activities.known_adls)
    ok = pd.DataFrame({"activity_code": ["D01", "D07"], "subject_id": ["SA01", "SA02"]})
    assert_no_unknown_in_training(ok, SPLITS, known)
    for code in ("F05", "D10"):
        bad = pd.DataFrame({"activity_code": ["D01", code], "subject_id": ["SA01", "SA01"]})
        with pytest.raises(LeakageError):
            assert_no_unknown_in_training(bad, SPLITS, known)


def test_guard2_rejects_non_train_subject(cfg):
    bad = pd.DataFrame({"activity_code": ["D01"], "subject_id": ["SA03"]})
    with pytest.raises(LeakageError):
        assert_no_unknown_in_training(bad, SPLITS, list(cfg.activities.known_adls))


def test_guard3():
    assert_scaler_fit_on_train({"fit_subjects": ["SA01"]}, SPLITS)
    with pytest.raises(LeakageError):
        assert_scaler_fit_on_train({"fit_subjects": ["SA01", "SE06"]}, SPLITS)
    with pytest.raises(LeakageError):
        assert_scaler_fit_on_train({"fit_subjects": []}, SPLITS)
