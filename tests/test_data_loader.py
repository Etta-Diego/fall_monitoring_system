from pathlib import Path

import numpy as np
import pytest

from fallmon.data_loader import build_index, load_trial, read_raw, to_physical

ROW = "256, 0, -256, 16, 0, -16, 1, 2, 3"  # ADXL: 256 counts = 1 g; ITG: 16 counts ~ 0.977 deg/s


def _write(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def test_reads_lines_with_and_without_semicolon_and_trailing_blank(tmp_path):
    p = _write(tmp_path / "SA01" / "D01_SA01_R01.txt", [ROW + ";", ROW, "  ", ""])
    raw = read_raw(p)
    assert raw.shape == (2, 9)
    assert raw[0, 0] == 256


def test_rejects_wrong_column_count(tmp_path):
    p = _write(tmp_path / "SA01" / "D01_SA01_R01.txt", [ROW + ";", "1, 2, 3;"])
    with pytest.raises(ValueError):
        read_raw(p)


def test_conversion_constants(cfg):
    raw = np.array([[256, 0, -256, 16, 0, -16, 9, 9, 9]])
    phys = to_physical(raw, cfg)
    assert phys.shape == (1, 6)  # MMA8451Q columns dropped
    np.testing.assert_allclose(phys[0, :3], [1.0, 0.0, -1.0])  # (2*16)/2^13 * 256 = 1 g
    np.testing.assert_allclose(phys[0, 3], 16 * 4000 / 2**16)  # (2*2000)/2^16 deg/s per count


def test_subject_taken_from_folder_not_filename(tmp_path, cfg):
    # Mirrors the real SA15/D17_SE15_R01.txt quirk (decision D-005).
    _write(tmp_path / "SA15" / "D17_SE15_R01.txt", [ROW + ";"])
    _write(tmp_path / "SE15" / "D17_SE15_R01.txt", [ROW + ";"])
    trial = load_trial(tmp_path / "SA15" / "D17_SE15_R01.txt", cfg)
    assert trial.subject_id == "SA15" and trial.age_group == "young"
    assert trial.trial_id == "D17_SA15_R01"
    index = build_index(tmp_path, cfg)
    assert sorted(index["trial_id"]) == ["D17_SA15_R01", "D17_SE15_R01"]
    assert index.set_index("trial_id").loc["D17_SA15_R01", "filename_subject_mismatch"]


def test_index_groups_and_durations(tmp_path, cfg):
    _write(tmp_path / "SA01" / "F05_SA01_R03.txt", [ROW + ";"] * 400)
    _write(tmp_path / "SE02" / "D10_SE02_R01.txt", [ROW + ";"] * 200)
    index = build_index(tmp_path, cfg).set_index("trial_id")
    assert index.loc["F05_SA01_R03", "activity_group"] == "fall"
    assert index.loc["F05_SA01_R03", "duration_s"] == 2.0
    assert index.loc["D10_SE02_R01", "activity_group"] == "unknown_adl"
    assert index.loc["D10_SE02_R01", "age_group"] == "elderly"
