"""Replay SisFall trials sample by sample as a simulated IoT stream (PRD 12.1).

Trials are chained back to back with no synthetic data in between; the processor resets
its state whenever the trial id changes.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from fallmon.data_loader import Trial

PACING_SLACK_S = 0.002  # only sleep when this far ahead of schedule


@dataclass(frozen=True)
class Sample:
    t_s: float  # time in trial
    raw_6ch: np.ndarray  # raw-rate (200 Hz) sample in physical units: ax, ay, az [g], gx, gy, gz [deg/s]
    trial_id: str
    subject_id: str


class StreamSimulator:
    def __init__(self, trials: list[Trial], speed: float = 1.0, realtime: bool = True):
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.trials = trials
        self.speed = speed
        self.realtime = realtime

    def __iter__(self) -> Iterator[Sample]:
        start = time.perf_counter()
        emitted = 0
        for trial in self.trials:
            for i, row in enumerate(trial.data):
                if self.realtime:
                    due = start + emitted / (trial.fs * self.speed)
                    ahead = due - time.perf_counter()
                    if ahead > PACING_SLACK_S:
                        time.sleep(ahead)
                yield Sample(i / trial.fs, row, trial.trial_id, trial.subject_id)
                emitted += 1
