"""Leakage guards and test lock (PRD Section 11). Further guards are added in later phases."""

from __future__ import annotations


class LeakageError(AssertionError):
    """Raised when a data-leakage rule is broken. Never catch and ignore this."""


def assert_no_subject_overlap(splits: dict) -> None:
    """Guard 1: every subject appears in exactly one of train / val / test."""
    seen: dict[str, str] = {}
    for part in ("train", "val", "test"):
        for subject in splits[part]:
            if subject in seen:
                raise LeakageError(f"subject {subject} is in both {seen[subject]} and {part}")
            seen[subject] = part


def assert_no_unknown_in_training(train_windows_index, splits: dict, known_adls: list[str]) -> None:
    """Guard 2: training windows come only from known ADLs of train-split subjects.

    `train_windows_index` has one row per training window with `activity_code` and `subject_id`.
    """
    bad_codes = set(train_windows_index["activity_code"]) - set(known_adls)
    if bad_codes:
        raise LeakageError(f"training windows contain non-known-ADL activities: {sorted(bad_codes)}")
    bad_subjects = set(train_windows_index["subject_id"]) - set(splits["train"])
    if bad_subjects:
        raise LeakageError(f"training windows contain subjects outside the train split: {sorted(bad_subjects)}")


def assert_scaler_fit_on_train(scaler_meta: dict, splits: dict) -> None:
    """Guard 3: the normalisation scaler was fitted on train-split subjects only."""
    fit_subjects = set(scaler_meta["fit_subjects"])
    if not fit_subjects:
        raise LeakageError("scaler metadata lists no fit subjects")
    outside = fit_subjects - set(splits["train"])
    if outside:
        raise LeakageError(f"scaler was fitted on subjects outside the train split: {sorted(outside)}")
