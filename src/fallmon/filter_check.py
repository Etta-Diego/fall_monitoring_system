"""Causal vs zero-phase low-pass filter check (PRD 6.1), on the validation split.

The system uses the causal filter for training and streaming (D-003). This check reports what
switching to offline zero-phase (filtfilt) filtering would change, without retraining:
1. delay introduced by the causal filter at typical movement frequencies;
2. DTE confidence when the (causally trained) models are fed zero-phase input;
3. impact peak height and timing on fall trials.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import signal
from sklearn.metrics import roc_auc_score

from fallmon import ood
from fallmon.config import Config
from fallmon.dte import DeepTimeEnsemble
from fallmon.preprocessing import ALL_CHANNELS, Scaler, design_lowpass
from fallmon.reporting import write_table
from fallmon.train import ensemble_step_outputs
from fallmon.windowing import load_processed

AM = ALL_CHANNELS.index("Am")
DELAY_FREQS_HZ = (1.0, 2.0, 5.0, 10.0)


def causal_group_delay_ms(cfg: Config) -> dict[float, float]:
    """Group delay of the causal Butterworth at a few frequencies, in milliseconds."""
    b, a = signal.sos2tf(design_lowpass(cfg))
    w, gd = signal.group_delay((b, a), w=list(DELAY_FREQS_HZ), fs=cfg.dataset.fs_raw)
    return {float(f): float(d / cfg.dataset.fs_raw * 1000) for f, d in zip(w, gd)}


def run_filter_check(index: pd.DataFrame, splits: dict, ens: DeepTimeEnsemble, scaler: Scaler, cfg: Config) -> pd.DataFrame:
    zero_cfg = cfg.model_copy(update={"preprocessing": cfg.preprocessing.model_copy(update={"offline_zero_phase": True})})
    groups = ["known_adl", "fall"]
    causal = load_processed(index, splits["val"], groups, cfg)
    zero = load_processed(index, splits["val"], groups, zero_cfg)

    sc = ensemble_step_outputs(ens, causal, scaler, cfg)
    sz = ensemble_step_outputs(ens, zero, scaler, cfg)
    thr = cfg.ood.threshold
    is_fall = (sc["activity_group"] == "fall").astype(int)
    rows = [{"check": f"causal filter group delay at {f:g} Hz [ms]", "causal": round(d, 2), "zero_phase": 0.0}
            for f, d in causal_group_delay_ms(cfg).items()]
    for name, s in (("causal", sc), ("zero_phase", sz)):
        s["ood"] = s["confidence"] < thr
    rows += [
        {"check": "step OOD rate, known ADLs", "causal": sc.loc[is_fall == 0, "ood"].mean(),
         "zero_phase": sz.loc[is_fall == 0, "ood"].mean()},
        {"check": "step OOD rate, falls", "causal": sc.loc[is_fall == 1, "ood"].mean(),
         "zero_phase": sz.loc[is_fall == 1, "ood"].mean()},
        {"check": "AUROC known vs fall (per step)",
         "causal": roc_auc_score(is_fall, ood.ood_score(sc["confidence"].to_numpy())),
         "zero_phase": roc_auc_score(is_fall, ood.ood_score(sz["confidence"].to_numpy()))},
        {"check": "mean |confidence difference| per step", "causal": 0.0,
         "zero_phase": float(np.abs(sc["confidence"].to_numpy() - sz["confidence"].to_numpy()).mean())},
    ]
    fs = cfg.preprocessing.target_fs
    peaks_c, peaks_z, shift_ms = [], [], []
    for c, z in zip(causal, zero):
        if c.activity_group != "fall":
            continue
        ic, iz = int(np.argmax(c.physical[:, AM])), int(np.argmax(z.physical[:, AM]))
        peaks_c.append(c.physical[ic, AM])
        peaks_z.append(z.physical[iz, AM])
        shift_ms.append((ic - iz) / fs * 1000)
    rows += [
        {"check": "fall impact peak Am, median [g]", "causal": float(np.median(peaks_c)), "zero_phase": float(np.median(peaks_z))},
        {"check": "fall impact peak time shift causal - zero-phase, median [ms]", "causal": float(np.median(shift_ms)),
         "zero_phase": 0.0},
        {"check": "fall impact peak time shift, max |shift| [ms]", "causal": float(np.max(np.abs(shift_ms))), "zero_phase": 0.0},
    ]
    table = pd.DataFrame(rows)
    table[["causal", "zero_phase"]] = table[["causal", "zero_phase"]].astype(float).round(4)
    write_table(table, "phase4_filter_check", "Causal vs zero-phase filter check (validation split)",
                "Models were trained on causally filtered data (D-003) and are NOT retrained here; the zero-phase "
                "column shows the effect of feeding zero-phase input to the same models. Peak time shift is at 50 Hz "
                "resolution (20 ms per sample).")
    return table
