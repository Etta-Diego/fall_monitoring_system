import json
from pathlib import Path

import pandas as pd
import pytest

from fallmon.splits import load_splits, make_splits, save_splits

REAL_SPLITS = Path("data/splits.json")


def _fake_index():
    rows = []
    for i in range(1, 24):
        s = f"SA{i:02d}"
        rows += [(s, "young", "known_adl"), (s, "young", "fall")]
    for i in range(1, 16):
        s = f"SE{i:02d}"
        rows.append((s, "elderly", "known_adl"))
        if s == "SE06":
            rows.append((s, "elderly", "fall"))
    df = pd.DataFrame(rows, columns=["subject_id", "age_group", "activity_group"])
    df["trial_id"] = [f"t{i}" for i in range(len(df))]
    return df


def test_sizes_no_overlap_and_force_test(cfg):
    s = make_splits(_fake_index(), cfg)
    young = {p: [x for x in s[p] if x.startswith("SA")] for p in ("train", "val", "test")}
    eld = {p: [x for x in s[p] if x.startswith("SE")] for p in ("train", "val", "test")}
    assert [len(young[p]) for p in ("train", "val", "test")] == [15, 4, 4]
    assert [len(eld[p]) for p in ("train", "val", "test")] == [9, 3, 3]
    all_subjects = s["train"] + s["val"] + s["test"]
    assert len(all_subjects) == len(set(all_subjects)) == 38
    assert "SE06" in s["test"]
    assert "SE06 forced to test" in s["notes"]


def test_deterministic(cfg):
    a, b = make_splits(_fake_index(), cfg), make_splits(_fake_index(), cfg)
    assert all(a[p] == b[p] for p in ("train", "val", "test"))


def test_wrong_subject_count_rejected(cfg):
    idx = _fake_index()
    with pytest.raises(ValueError):
        make_splits(idx[idx["subject_id"] != "SA01"], cfg)


def test_save_refuses_overwrite(tmp_path, cfg):
    s = make_splits(_fake_index(), cfg)
    p = tmp_path / "splits.json"
    save_splits(s, p)
    with pytest.raises(FileExistsError):
        save_splits(s, p)
    save_splits(s, p, force=True)
    assert load_splits(p)["test"] == s["test"]


@pytest.mark.skipif(not REAL_SPLITS.exists(), reason="data/splits.json not generated yet")
def test_committed_splits_file():
    s = load_splits(REAL_SPLITS)
    assert "SE06" in s["test"]
    assert len(s["train"]) + len(s["val"]) + len(s["test"]) == 38
