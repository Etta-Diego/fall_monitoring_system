"""Load preprocessed trials for a partition and cut sliding windows for DTE training (PRD 8.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fallmon.config import Config
from fallmon.data_loader import load_trial
from fallmon.preprocessing import ALL_CHANNELS, Scaler, channel_indices, preprocess

STATIC_CLASS = "static"
AM, GM = ALL_CHANNELS.index("Am"), ALL_CHANNELS.index("Gm")


@dataclass(frozen=True)
class ProcessedTrial:
    trial_id: str
    subject_id: str
    age_group: str
    activity_code: str
    activity_group: str
    physical: np.ndarray  # (m, 8) filtered, 50 Hz, physical units, ALL_CHANNELS order


def load_processed(index: pd.DataFrame, subjects: list[str], groups: list[str], cfg: Config) -> list[ProcessedTrial]:
    """Load and preprocess every trial of the given subjects whose activity group is in `groups`."""
    rows = index[index["subject_id"].isin(subjects) & index["activity_group"].isin(groups)]
    out = []
    for row in rows.itertuples():
        trial = load_trial(Path(cfg.dataset.raw_dir) / row.path, cfg)
        out.append(
            ProcessedTrial(
                trial.trial_id, trial.subject_id, trial.age_group, trial.activity_code,
                trial.activity_group, preprocess(trial.data, cfg),
            )
        )
    return out


def model_input(trial: ProcessedTrial, scaler: Scaler, cfg: Config) -> np.ndarray:
    """Select the configured model channels and z-score them: (m, n_channels)."""
    return scaler.transform(trial.physical[:, channel_indices(cfg)])


def class_names(cfg: Config) -> list[str]:
    """Classifier output classes for the configured label scheme."""
    if cfg.dte.label_scheme == "activity":
        return list(cfg.activities.known_adls)
    return list(cfg.activities.class_groups) + [STATIC_CLASS]


def is_static(physical_window: np.ndarray, cfg: Config) -> bool:
    """Person is still for the whole window: low Am variation and low rotation (physical units)."""
    st = cfg.dte.static
    return bool(physical_window[:, AM].std() < st.am_std_g and physical_window[:, GM].mean() < st.gm_mean_dps)


def window_label(physical_window: np.ndarray, activity_code: str, cfg: Config) -> str:
    """Training label of one known-ADL window (D-009)."""
    if cfg.dte.label_scheme == "activity":
        return activity_code
    if is_static(physical_window, cfg):
        return STATIC_CLASS
    return next(g for g, codes in cfg.activities.class_groups.items() if activity_code in codes)


def window_starts(n_samples: int, length: int, stride: int, cap: int) -> np.ndarray:
    """Start indices of all full windows; evenly thinned to at most `cap` (long trials such as D01-D04)."""
    starts = np.arange(0, n_samples - length + 1, stride)
    if len(starts) > cap:
        starts = starts[np.unique(np.linspace(0, len(starts) - 1, cap).round().astype(int))]
    return starts


def make_windows(
    trials: list[ProcessedTrial], length: int, scaler: Scaler, cfg: Config
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Windows (N, n_channels, length) float32, labels (N,), and one metadata row per window."""
    stride = cfg.samples(cfg.dte.train_stride_s)
    class_idx = {c: i for i, c in enumerate(class_names(cfg))}
    xs, ys, meta = [], [], []
    for tr in trials:
        x = model_input(tr, scaler, cfg)
        for s in window_starts(len(x), length, stride, cfg.dte.max_windows_per_trial):
            label = window_label(tr.physical[s : s + length], tr.activity_code, cfg)
            xs.append(x[s : s + length].T)
            ys.append(class_idx[label])
            meta.append((tr.trial_id, tr.subject_id, tr.activity_code, tr.activity_group, int(s), label))
    meta_df = pd.DataFrame(meta, columns=["trial_id", "subject_id", "activity_code", "activity_group", "start", "label"])
    return np.stack(xs).astype(np.float32), np.array(ys, dtype=np.int64), meta_df


def decision_step_ends(n_samples: int, cfg: Config) -> np.ndarray:
    """Exclusive end index of each decision step in a trial (PRD 8.3).

    The first decision is made once the longest window is full; then every decision_stride_s.
    Decision time of a step = end / target_fs.
    """
    first = max(cfg.samples(w) for w in cfg.dte.window_lengths_s)
    return np.arange(first, n_samples + 1, cfg.samples(cfg.stream.decision_stride_s))
