"""Synthetic 200 Hz signals in physical units (g, deg/s) for verifier and pipeline tests."""

import numpy as np

from fallmon.data_loader import Trial

FS = 200


def standing(seconds: float) -> np.ndarray:
    d = np.zeros((int(seconds * FS), 6))
    d[:, 2] = 1.0  # gravity on z (upright)
    return d


def add_impact(d: np.ndarray, t_s: float, peak_g: float, axis: int = 2, dur_s: float = 0.06) -> None:
    i = int(t_s * FS)
    d[i:i + int(dur_s * FS), axis] = peak_g


def fall_signal(seconds: float = 15.0, t_impact: float = 6.4) -> np.ndarray:
    """Upright, rotate, hard impact, then lying still with gravity on x (90 deg change)."""
    d = standing(seconds)
    i0, i1 = int((t_impact - 0.4) * FS), int(t_impact * FS)
    d[i0:i1, 3] = 200.0  # rotation while falling
    d[i0:i1, 2] = 0.4    # partial free fall
    after = int((t_impact + 0.06) * FS)
    d[after:, 2], d[after:, 0] = 0.0, 1.0  # lying
    add_impact(d, t_impact, 3.0, axis=0)
    add_impact(d, t_impact, 2.5, axis=2)
    return d


def hard_sit_signal(seconds: float = 12.0, t_impact: float = 6.0) -> np.ndarray:
    """Upright, hard sit (impact ~3 g, small tilt), then gets up and walks: not still afterwards."""
    d = standing(seconds)
    after = int((t_impact + 0.06) * FS)
    d[after:, 0], d[after:, 2] = np.sin(np.radians(15)), np.cos(np.radians(15))
    add_impact(d, t_impact, 3.0, axis=2)
    walk = int((t_impact + 1.0) * FS)
    t = np.arange(len(d) - walk) / FS
    d[walk:, 2] += 0.4 * np.sin(2 * np.pi * 2 * t)
    d[walk:, 4] = 30.0
    return d


def as_trial(data: np.ndarray, trial_id: str, group: str = "fall") -> Trial:
    return Trial(trial_id, trial_id.split("_")[1], "young", trial_id[:3], group, 1, FS, data)
