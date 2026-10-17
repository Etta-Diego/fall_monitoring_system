import numpy as np
import pandas as pd
import pytest

from fallmon.evaluation import _rates, bootstrap_ci, end_to_end_metrics, mcnemar_test


def _outcomes(groups, alerts, durations=None, delays=None):
    n = len(groups)
    return pd.DataFrame({
        "trial_id": [f"t{i}" for i in range(n)], "activity_group": groups, "alerts": alerts,
        "alerted": np.array(alerts) > 0, "duration_s": durations or [3600.0] * n,
        "first_alert_minus_impact_s": delays or [np.nan] * n,
    })


def test_rates_hand_computed():
    g = np.array(["fall", "fall", "fall", "fall", "known_adl", "known_adl", "unknown_adl", "unknown_adl"])
    a = np.array([True, True, True, False, True, False, True, True])
    r = _rates(a, g)
    assert (r["tp"], r["fn"], r["fp"], r["tn"]) == (3, 1, 3, 1)
    assert r["sensitivity"] == 0.75 and r["precision"] == 0.5 and r["specificity"] == 0.25
    assert r["fpr_known"] == 0.5 and r["fpr_unknown"] == 1.0
    assert r["f1"] == pytest.approx(2 * 0.5 * 0.75 / 1.25)
    assert r["accuracy"] == 0.5


def test_false_alerts_per_hour_counts_alerts_not_trials():
    o = _outcomes(["fall", "known_adl", "known_adl"], [1, 3, 0], durations=[15.0, 1800.0, 1800.0],
                  delays=[1.5, np.nan, np.nan])
    m = end_to_end_metrics(o)
    assert m["false_alerts"] == 3 and m["nonfall_hours"] == 1.0 and m["false_alerts_per_hour"] == 3.0
    assert m["delay_median_s"] == 1.5 and m["early_alert_share"] == 0.0


def test_bootstrap_ci_contains_point_estimate_and_is_seeded():
    rng = np.random.default_rng(0)
    groups = ["fall"] * 50 + ["known_adl"] * 50
    alerts = list((rng.random(50) < 0.9).astype(int)) + list((rng.random(50) < 0.1).astype(int))
    o = _outcomes(groups, alerts)
    ci1, ci2 = bootstrap_ci(o, 200, 42), bootstrap_ci(o, 200, 42)
    assert np.allclose(np.array(list(ci1.values())), np.array(list(ci2.values())), equal_nan=True)
    sens = _rates(o["alerted"].to_numpy(), o["activity_group"].to_numpy())["sensitivity"]
    assert ci1["sensitivity"][0] <= sens <= ci1["sensitivity"][1]


def test_mcnemar_pairs_trials():
    base = _outcomes(["known_adl"] * 10, [1] * 10)  # baseline alerts on all 10 non-falls (all wrong)
    prop = _outcomes(["known_adl"] * 10, [0] * 9 + [1])  # proposed fixes 9
    r = mcnemar_test(base, prop, group_is_fall=False)
    assert (r["both_correct"], r["baseline_only_correct"], r["proposed_only_correct"], r["both_wrong"]) == (0, 0, 9, 1)
    assert r["p_value"] < 0.01
