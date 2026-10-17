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
