"""Low-pass filter, downsample, derived magnitudes and z-score normalisation (PRD Section 6).

The same functions are used offline (training) and in the stream, so there is no
train/serve skew. By default both use the causal filter (decision D-003).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

from fallmon.config import Config

RAW_CHANNELS = ["ax", "ay", "az", "gx", "gy", "gz"]
ALL_CHANNELS = RAW_CHANNELS + ["Am", "Gm"]


def design_lowpass(cfg: Config) -> np.ndarray:
    """Butterworth low-pass as second-order sections, designed at the raw sampling rate."""
    p = cfg.preprocessing
    return signal.butter(p.filter_order, p.lowpass_hz, btype="low", fs=cfg.dataset.fs_raw, output="sos")


def initial_state(sos: np.ndarray, first_sample: np.ndarray) -> np.ndarray:
    """Filter state as if the signal had been constant at its first value (avoids a start-up transient)."""
    zi = signal.sosfilt_zi(sos)  # (n_sections, 2)
    return zi[:, :, None] * first_sample[None, None, :]  # (n_sections, 2, n_channels)


def lowpass(data: np.ndarray, cfg: Config) -> np.ndarray:
    """Filter a whole trial (n, c). Causal unless preprocessing.offline_zero_phase is set."""
    sos = design_lowpass(cfg)
    if cfg.preprocessing.offline_zero_phase:
        return signal.sosfiltfilt(sos, data, axis=0)
    filtered, _ = signal.sosfilt(sos, data, axis=0, zi=initial_state(sos, data[0]))
    return filtered


def decimate(data: np.ndarray, cfg: Config) -> np.ndarray:
    """Keep every k-th sample (k = fs_raw / target_fs), starting at the first. Filter first."""
    return data[:: cfg.decimation_factor]


def add_magnitudes(data6: np.ndarray) -> np.ndarray:
    """(n, 6) -> (n, 8): append Am = |acc| [g] and Gm = |gyro| [deg/s]."""
    am = np.linalg.norm(data6[:, 0:3], axis=1, keepdims=True)
    gm = np.linalg.norm(data6[:, 3:6], axis=1, keepdims=True)
    return np.hstack([data6, am, gm])


def channel_indices(cfg: Config) -> list[int]:
    unknown = set(cfg.preprocessing.channels) - set(ALL_CHANNELS)
    if unknown:
        raise ValueError(f"unknown channels in config: {sorted(unknown)}")
    return [ALL_CHANNELS.index(c) for c in cfg.preprocessing.channels]


def preprocess(data6: np.ndarray, cfg: Config) -> np.ndarray:
    """Raw-rate physical signal (n, 6) -> filtered, downsampled (m, 8) in physical units.

    Columns are always ALL_CHANNELS order; the verifier uses this unnormalised output.
    """
    return add_magnitudes(decimate(lowpass(data6, cfg), cfg))


class StreamingPreprocessor:
    """Sample-by-sample version of `preprocess` with the causal filter (for the stream)."""

    def __init__(self, cfg: Config):
        self.sos = design_lowpass(cfg)
        self.factor = cfg.decimation_factor
        self.reset()

    def reset(self) -> None:
        self.zi: np.ndarray | None = None
        self.count = 0

    def push(self, sample6: np.ndarray) -> np.ndarray | None:
        """Feed one raw-rate sample (6,). Returns an (8,) output sample every `factor` inputs, else None."""
        x = np.asarray(sample6, dtype=np.float64)
        if self.zi is None:
            self.zi = initial_state(self.sos, x)
        y, self.zi = signal.sosfilt(self.sos, x[None, :], axis=0, zi=self.zi)
        keep = self.count % self.factor == 0
        self.count += 1
        return add_magnitudes(y)[0] if keep else None


@dataclass
class Scaler:
    """Per-channel z-score. Fit on training-split known-ADL windows only (PRD 6, guard 3)."""

    channels: list[str]
    mean: np.ndarray
    std: np.ndarray
    fit_subjects: list[str]

    @classmethod
    def fit(cls, data: np.ndarray, channels: list[str], fit_subjects: list[str]) -> Scaler:
        """`data` is (n_samples, n_channels), e.g. all training windows stacked on the time axis."""
        std = data.std(axis=0)
        std[std == 0] = 1.0
        return cls(list(channels), data.mean(axis=0), std, sorted(fit_subjects))

    def transform(self, data: np.ndarray) -> np.ndarray:
        return (data - self.mean) / self.std

    def save(self, path: str | Path) -> None:
        payload = {
            "channels": self.channels,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "fit_subjects": self.fit_subjects,
        }
        Path(path).write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> Scaler:
        d = json.loads(Path(path).read_text())
        return cls(d["channels"], np.array(d["mean"]), np.array(d["std"]), d["fit_subjects"])
