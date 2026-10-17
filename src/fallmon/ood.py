"""Max-softmax confidence and OOD decision (PRD 8.3, 8.4). Same threshold for baseline and proposed (D-002)."""

from __future__ import annotations

import numpy as np


def confidence(p_ens: np.ndarray) -> np.ndarray:
    """Maximum ensemble softmax probability per step."""
    return p_ens.max(axis=1)


def predicted_class(p_ens: np.ndarray) -> np.ndarray:
    return p_ens.argmax(axis=1)


def is_ood(conf: np.ndarray, threshold: float) -> np.ndarray:
    """Low confidence = out-of-distribution = probable fall in the baseline."""
    return conf < threshold


def ood_score(conf: np.ndarray) -> np.ndarray:
    """Higher = more OOD. Used for AUROC/AUPRC reporting only."""
    return 1.0 - conf


def threshold_at_tpr(known_conf: np.ndarray, tpr: float = 0.95) -> float:
    """Threshold at which a fraction `tpr` of known-ADL steps are kept as in-distribution.

    Reported as a sensitivity note only; never used for decisions (PRD 8.4).
    """
    return float(np.quantile(known_conf, 1.0 - tpr))
