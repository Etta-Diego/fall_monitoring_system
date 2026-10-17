import pytest

from fallmon.guards import LeakageError, assert_no_subject_overlap


def test_overlap_detected():
    with pytest.raises(LeakageError):
        assert_no_subject_overlap({"train": ["SA01", "SA02"], "val": ["SA03"], "test": ["SA02"]})


def test_disjoint_passes():
    assert_no_subject_overlap({"train": ["SA01"], "val": ["SA02"], "test": ["SE06"]})


def test_test_lock():
    from fallmon.guards import TestLockError, assert_not_test

    splits = {"train": ["SA01"], "val": ["SA02"], "test": ["SE06"]}
    assert_not_test(["SA01", "SA02"], splits, "x")
    with pytest.raises(TestLockError):
        assert_not_test(["SA01", "SE06"], splits, "x")


def test_guard4_verifier_tuning_data():
    import pandas as pd

    from fallmon.guards import assert_verifier_tuned_without_test_or_unknown

    splits = {"train": ["SA01"], "val": ["SA02", "SE05"], "test": ["SE06"]}
    ok = pd.DataFrame({"subject_id": ["SA02", "SE05"], "activity_group": ["known_adl", "fall"]})
    assert_verifier_tuned_without_test_or_unknown(ok, splits)
    for bad in (pd.DataFrame({"subject_id": ["SA02"], "activity_group": ["unknown_adl"]}),
                pd.DataFrame({"subject_id": ["SE06"], "activity_group": ["fall"]}),
                pd.DataFrame({"subject_id": ["SA01"], "activity_group": ["known_adl"]})):
        with pytest.raises(LeakageError):
            assert_verifier_tuned_without_test_or_unknown(bad, splits)
