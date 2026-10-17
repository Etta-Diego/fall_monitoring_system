"""Deep Time Ensemble (DTE): reimplementation of Roy et al. (2023) from the paper's description (D-007).

Three small 1D-CNNs, one per window length, trained on known ADLs only. At each decision step
the ensemble averages their softmax outputs (PRD 8.2, 8.3).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


class CNN1D(nn.Module):
    """PRD 8.2 architecture. Input (batch, channels, time)."""

    def __init__(self, in_channels: int, n_classes: int, dropout: float):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=5, padding=2), nn.BatchNorm1d(32), nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2), nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 64, kernel_size=3, padding=1), nn.BatchNorm1d(64), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),  # global average pooling over time
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(dropout), nn.Linear(64, n_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


def model_filename(window_s: float) -> str:
    return f"dte_w{window_s:.1f}s.pt"


class DeepTimeEnsemble:
    def __init__(self, models: list[CNN1D], window_samples: list[int], classes: list[str]):
        self.models = models
        self.window_samples = window_samples
        self.classes = classes
        for m in self.models:
            m.eval()

    @torch.no_grad()
    def predict_steps(self, x: np.ndarray, step_ends: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Ensemble probabilities at each decision step.

        x: normalised model input (m, n_channels). step_ends: exclusive end index of each step.
        Each model sees the latest window of its own length ending at the step.
        Returns (p_ens (S, K), per_model (n_models, S, K)).
        """
        per_model = []
        for model, length in zip(self.models, self.window_samples):
            windows = np.stack([x[e - length : e].T for e in step_ends]).astype(np.float32)
            per_model.append(torch.softmax(model(torch.from_numpy(windows)), dim=1).numpy())
        per_model = np.stack(per_model)
        return per_model.mean(axis=0), per_model

    def save(self, model_dir: Path, window_lengths_s: list[float], meta: dict) -> None:
        model_dir.mkdir(parents=True, exist_ok=True)
        for model, w in zip(self.models, window_lengths_s):
            torch.save(model.state_dict(), model_dir / model_filename(w))
        (model_dir / "dte_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    @classmethod
    def load(cls, model_dir: Path) -> tuple[DeepTimeEnsemble, dict]:
        meta = json.loads((model_dir / "dte_meta.json").read_text())
        models = []
        for w in meta["window_lengths_s"]:
            m = CNN1D(len(meta["channels"]), len(meta["classes"]), meta["dropout"])
            m.load_state_dict(torch.load(model_dir / model_filename(w), weights_only=True))
            models.append(m)
        return cls(models, meta["window_samples"], meta["classes"]), meta
