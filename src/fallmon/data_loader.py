"""Parse SisFall files, convert raw sensor counts to physical units, build the trial index.

Data source: SisFall dataset replay (simulated IoT stream). Verified file-format facts
are recorded in doc/dataset_notes.md.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fallmon.config import Config

log = logging.getLogger(__name__)

FILENAME_RE = re.compile(r"^(?P<activity>[DF]\d{2})_(?P<subject>S[AE]\d{2})_R(?P<trial>\d{2})\.txt$")
SUBJECT_DIR_RE = re.compile(r"^S[AE]\d{2}$")
N_RAW_COLUMNS = 9  # ADXL345 xyz, ITG3200 xyz, MMA8451Q xyz
USED_COLUMNS = slice(0, 6)  # MMA8451Q (columns 7-9) is ignored (PRD 5.1)


@dataclass(frozen=True)
class Trial:
    trial_id: str  # canonical "<ACT>_<SUBJECT>_R<NN>", subject taken from the folder
    subject_id: str
    age_group: str  # "young" | "elderly"
    activity_code: str
    activity_group: str  # "known_adl" | "unknown_adl" | "fall"
    trial_no: int
    fs: int
    data: np.ndarray  # (n, 6): ax, ay, az [g], gx, gy, gz [deg/s]


def age_group_of(subject_id: str) -> str:
    if subject_id.startswith("SA"):
        return "young"
    if subject_id.startswith("SE"):
        return "elderly"
    raise ValueError(f"unrecognised subject id {subject_id!r}")


def parse_filename(path: Path) -> tuple[str, str, int]:
    """Return (activity_code, subject_id_in_filename, trial_no)."""
    m = FILENAME_RE.match(path.name)
    if m is None:
        raise ValueError(f"file name does not match SisFall pattern: {path.name}")
    return m["activity"], m["subject"], int(m["trial"])


def read_raw(path: Path) -> np.ndarray:
    """Read one SisFall file as an (n, 9) int array of raw sensor counts.

    Handles the quirks found in the real files: lines may or may not end with ';',
    and some files end with blank lines.
    """
    text = path.read_text(encoding="ascii")
    n_lines = sum(1 for line in text.splitlines() if line.strip())
    values = np.array(text.replace(";", " ").replace(",", " ").split(), dtype=np.int32)
    if values.size != n_lines * N_RAW_COLUMNS:
        raise ValueError(f"{path}: expected {N_RAW_COLUMNS} values on each of {n_lines} lines, got {values.size}")
    return values.reshape(n_lines, N_RAW_COLUMNS)


def count_samples(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(1 for line in f if line.strip())


def conversion_factors(cfg: Config) -> np.ndarray:
    """Per-column scale for the 6 used columns: [(2 * range) / 2**bits] (SisFall readme)."""
    acc, gyro = cfg.dataset.sensors.adxl345, cfg.dataset.sensors.itg3200
    k_acc = (2 * acc.range_g) / (2**acc.bits)
    k_gyro = (2 * gyro.range_dps) / (2**gyro.bits)
    return np.array([k_acc] * 3 + [k_gyro] * 3)


def to_physical(raw: np.ndarray, cfg: Config) -> np.ndarray:
    """Convert (n, 9) raw counts to (n, 6) float: acceleration in g, rotation in deg/s."""
    return raw[:, USED_COLUMNS].astype(np.float64) * conversion_factors(cfg)


def subject_from_path(path: Path) -> str:
    """Subject comes from the folder, not the file name (decision D-005)."""
    folder = path.parent.name
    if not SUBJECT_DIR_RE.match(folder):
        raise ValueError(f"{path}: parent folder {folder!r} is not a SisFall subject folder")
    return folder


def load_trial(path: str | Path, cfg: Config) -> Trial:
    path = Path(path)
    activity, _, trial_no = parse_filename(path)
    subject = subject_from_path(path)
    return Trial(
        trial_id=f"{activity}_{subject}_R{trial_no:02d}",
        subject_id=subject,
        age_group=age_group_of(subject),
        activity_code=activity,
        activity_group=cfg.activities.group_of(activity),
        trial_no=trial_no,
        fs=cfg.dataset.fs_raw,
        data=to_physical(read_raw(path), cfg),
    )


def build_index(raw_dir: str | Path, cfg: Config) -> pd.DataFrame:
    """One row per trial file found under raw_dir. Works from the files actually present."""
    raw_dir = Path(raw_dir)
    rows = []
    for path in sorted(raw_dir.glob("S[AE][0-9][0-9]/*.txt")):
        activity, name_subject, trial_no = parse_filename(path)
        subject = subject_from_path(path)
        if name_subject != subject:
            log.warning("%s: file name says %s but folder is %s; using folder (D-005)", path.name, name_subject, subject)
        n = count_samples(path)
        rows.append(
            {
                "trial_id": f"{activity}_{subject}_R{trial_no:02d}",
                "subject_id": subject,
                "age_group": age_group_of(subject),
                "activity_code": activity,
                "activity_group": cfg.activities.group_of(activity),
                "trial_no": trial_no,
                "n_samples": n,
                "duration_s": n / cfg.dataset.fs_raw,
                "path": str(path.relative_to(raw_dir)),
                "filename_subject_mismatch": name_subject != subject,
            }
        )
    if not rows:
        raise FileNotFoundError(f"no SisFall trial files found under {raw_dir}")
    index = pd.DataFrame(rows)
    if index["trial_id"].duplicated().any():
        dupes = index.loc[index["trial_id"].duplicated(keep=False), "path"].tolist()
        raise ValueError(f"duplicate trial ids: {dupes}")
    return index


def dataset_summary(index: pd.DataFrame) -> pd.DataFrame:
    """Trials and recording hours per activity group and age group."""
    summary = (
        index.groupby(["activity_group", "age_group"])
        .agg(subjects=("subject_id", "nunique"), trials=("trial_id", "count"), hours=("duration_s", "sum"))
        .reset_index()
    )
    summary["hours"] = (summary["hours"] / 3600).round(2)
    return summary
