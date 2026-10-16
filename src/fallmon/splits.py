"""Participant-level train / validation / test split (PRD Section 7)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from fallmon.config import Config
from fallmon.guards import assert_no_subject_overlap

log = logging.getLogger(__name__)

PARTITIONS = ("train", "val", "test")


def make_splits(index: pd.DataFrame, cfg: Config) -> dict:
    """Assign every subject in the index to exactly one partition, per age group, seeded.

    Subjects in `split.force_test` go to test first; the rest are shuffled and dealt out.
    """
    rng = np.random.default_rng(cfg.seed)
    parts: dict[str, list[str]] = {p: [] for p in PARTITIONS}
    notes = []
    for age_group, sizes in (("young", cfg.split.young), ("elderly", cfg.split.elderly)):
        subjects = sorted(index.loc[index["age_group"] == age_group, "subject_id"].unique())
        wanted = sizes.train + sizes.val + sizes.test
        if wanted != len(subjects):
            raise ValueError(f"{age_group}: split sizes sum to {wanted} but {len(subjects)} subjects were found")

        forced = [s for s in cfg.split.force_test if s in subjects]
        if len(forced) > sizes.test:
            raise ValueError(f"{age_group}: more forced test subjects than test slots")
        for s in forced:
            n_falls = int(((index["subject_id"] == s) & (index["activity_group"] == "fall")).sum())
            note = f"{s} forced to test ({n_falls} fall trials; config split.force_test)"
            log.info(note)
            notes.append(note)

        rest = [s for s in subjects if s not in forced]
        rest = list(rng.permutation(rest))
        n_test = sizes.test - len(forced)
        parts["test"] += forced + rest[:n_test]
        parts["val"] += rest[n_test : n_test + sizes.val]
        parts["train"] += rest[n_test + sizes.val :]

    for missing in set(cfg.split.force_test) - set(index["subject_id"]):
        notes.append(f"{missing} listed in split.force_test but not found in the dataset")

    splits = {
        "seed": cfg.seed,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **{p: sorted(parts[p]) for p in PARTITIONS},
        "notes": "; ".join(notes),
    }
    assert_no_subject_overlap(splits)
    return splits


def save_splits(splits: dict, path: str | Path, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to regenerate (PRD 7.1)")
    path.write_text(json.dumps(splits, indent=2) + "\n")


def load_splits(path: str | Path) -> dict:
    splits = json.loads(Path(path).read_text())
    assert_no_subject_overlap(splits)
    return splits


def partition_of(splits: dict) -> dict[str, str]:
    """Map subject_id -> partition name."""
    return {s: p for p in PARTITIONS for s in splits[p]}


def splits_summary(index: pd.DataFrame, splits: dict) -> pd.DataFrame:
    """Subjects and trials per partition, age group and activity group."""
    df = index.assign(partition=index["subject_id"].map(partition_of(splits)))
    counts = df.pivot_table(
        index=["partition", "age_group"],
        columns="activity_group",
        values="trial_id",
        aggfunc="count",
        fill_value=0,
    )
    counts.insert(0, "subjects", df.groupby(["partition", "age_group"])["subject_id"].nunique())
    order = {p: i for i, p in enumerate(PARTITIONS)}
    counts = counts.reset_index().sort_values(["partition", "age_group"], key=lambda c: c.map(order).fillna(c))
    counts.columns.name = None
    return counts.reset_index(drop=True)
