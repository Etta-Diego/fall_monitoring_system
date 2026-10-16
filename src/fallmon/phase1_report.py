"""Phase 1 sanity outputs: unit-conversion check and example signal plots (train subjects only)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fallmon.config import Config
from fallmon.data_loader import load_trial
from fallmon.preprocessing import ALL_CHANNELS, preprocess
from fallmon.reporting import DATA_SOURCE, FIGURE_DPI, FIGURES_DIR

REST_ACTIVITY = "D07"  # trial starts standing still
REST_SECONDS = 1.0
EXAMPLE_ACTIVITIES = [("fall", "F01"), ("known_adl", "D07"), ("unknown_adl", "D10")]


def _train_rows(index: pd.DataFrame, splits: dict) -> pd.DataFrame:
    return index[index["subject_id"].isin(splits["train"])]


def rest_check(index: pd.DataFrame, splits: dict, cfg: Config) -> dict:
    """Mean Am over the first second of each train-split D07 trial; should be close to 1 g."""
    rows = _train_rows(index, splits)
    rows = rows[rows["activity_code"] == REST_ACTIVITY]
    n_rest = int(REST_SECONDS * cfg.dataset.fs_raw)
    means = []
    for rel in rows["path"]:
        acc = load_trial(Path(cfg.dataset.raw_dir) / rel, cfg).data[:n_rest, 0:3]
        means.append(np.linalg.norm(acc, axis=1).mean())
    means = np.array(means)
    return {"n": len(means), "mean": means.mean(), "min": means.min(), "max": means.max()}


def plot_examples(index: pd.DataFrame, splits: dict, cfg: Config) -> Path:
    """Am and Gm for one fall, one known ADL and one unknown ADL from the first young train subject."""
    rows = _train_rows(index, splits)
    subject = sorted(rows.loc[rows["age_group"] == "young", "subject_id"].unique())[0]
    fig, axes = plt.subplots(len(EXAMPLE_ACTIVITIES), 1, figsize=(8, 7), sharex=False)
    am_i, gm_i = ALL_CHANNELS.index("Am"), ALL_CHANNELS.index("Gm")
    for ax, (group, code) in zip(axes, EXAMPLE_ACTIVITIES):
        row = rows[(rows["subject_id"] == subject) & (rows["activity_code"] == code)].sort_values("trial_no").iloc[0]
        trial = load_trial(Path(cfg.dataset.raw_dir) / row["path"], cfg)
        x = preprocess(trial.data, cfg)
        t = np.arange(len(x)) / cfg.preprocessing.target_fs
        ax.plot(t, x[:, am_i], color="tab:blue", lw=1)
        ax.set_ylabel("Am [g]", color="tab:blue")
        ax2 = ax.twinx()
        ax2.plot(t, x[:, gm_i], color="tab:orange", lw=0.8, alpha=0.7)
        ax2.set_ylabel("Gm [deg/s]", color="tab:orange")
        ax.set_title(f"{trial.trial_id}  ({group.replace('_', ' ')})", fontsize=10)
    axes[-1].set_xlabel("Time in trial [s]")
    fig.suptitle(f"Example trials, filtered and downsampled to {cfg.preprocessing.target_fs} Hz\n{DATA_SOURCE}", fontsize=10)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURES_DIR / "phase1_examples.png"
    fig.savefig(out, dpi=FIGURE_DPI)
    plt.close(fig)
    return out
