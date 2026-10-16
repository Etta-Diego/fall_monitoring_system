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
