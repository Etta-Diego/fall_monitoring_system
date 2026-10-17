"""Train the Deep Time Ensemble on train-split known ADLs; early stopping on validation (PRD 8)."""

from __future__ import annotations

import copy
import logging
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from fallmon import ood
from fallmon.config import Config
from fallmon.dte import CNN1D, DeepTimeEnsemble
from fallmon.guards import assert_no_unknown_in_training, assert_scaler_fit_on_train
from fallmon.preprocessing import Scaler, channel_indices
from fallmon.reporting import DATA_SOURCE, FIGURE_DPI, FIGURES_DIR, write_table
from fallmon.utils import git_hash, seed_everything
from fallmon.windowing import (ProcessedTrial, class_names, decision_step_ends, load_processed, make_windows,
                               model_input, window_label)

log = logging.getLogger(__name__)

MODEL_DIR = Path("models")
SCALER_PATH = MODEL_DIR / "scaler.json"


def fit_scaler(train_trials: list[ProcessedTrial], cfg: Config) -> Scaler:
    """Fit the z-score on every sample of the train-split known-ADL trials (the data windows are cut from)."""
    data = np.vstack([t.physical[:, channel_indices(cfg)] for t in train_trials])
    return Scaler.fit(data, cfg.preprocessing.channels, sorted({t.subject_id for t in train_trials}))


def _evaluate(model: nn.Module, x: torch.Tensor, y: torch.Tensor, batch: int) -> tuple[float, float]:
    """Mean cross-entropy and macro F1 on a window set."""
    model.eval()
    losses, preds = [], []
    with torch.no_grad():
        for i in range(0, len(x), batch):
            logits = model(x[i : i + batch])
            losses.append(nn.functional.cross_entropy(logits, y[i : i + batch], reduction="sum").item())
            preds.append(logits.argmax(1))
    pred = torch.cat(preds).numpy()
    return sum(losses) / len(x), f1_score(y.numpy(), pred, average="macro")


def train_one(
    xtr: np.ndarray, ytr: np.ndarray, xva: np.ndarray, yva: np.ndarray, n_classes: int, cfg: Config, seed: int
) -> tuple[CNN1D, list[dict]]:
    """Train one CNN with Adam; keep the epoch with the best validation macro F1 (patience from config)."""
    d = cfg.dte
    torch.manual_seed(seed)
    model = CNN1D(xtr.shape[1], n_classes, d.dropout)
    opt = torch.optim.Adam(model.parameters(), lr=d.lr, weight_decay=d.weight_decay)
    gen = torch.Generator().manual_seed(seed)
    loader = DataLoader(TensorDataset(torch.from_numpy(xtr), torch.from_numpy(ytr)),
                        batch_size=d.batch_size, shuffle=True, generator=gen)
    xva_t, yva_t = torch.from_numpy(xva), torch.from_numpy(yva)

    best_f1, best_state, since_best, history = -1.0, None, 0, []
    for epoch in range(1, d.epochs + 1):
        model.train()
        total, n = 0.0, 0
        for xb, yb in loader:
            opt.zero_grad()
            loss = nn.functional.cross_entropy(model(xb), yb)
            loss.backward()
            opt.step()
            total += loss.item() * len(xb)
            n += len(xb)
        val_loss, val_f1 = _evaluate(model, xva_t, yva_t, d.batch_size)
        history.append({"epoch": epoch, "train_loss": total / n, "val_loss": val_loss, "val_macro_f1": val_f1})
        log.info("  epoch %2d  train_loss %.4f  val_loss %.4f  val_macroF1 %.4f", epoch, total / n, val_loss, val_f1)
        if val_f1 > best_f1:
            best_f1, best_state, since_best = val_f1, copy.deepcopy(model.state_dict()), 0
        else:
            since_best += 1
            if since_best >= d.patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, history


def ensemble_step_outputs(
    ens: DeepTimeEnsemble, trials: list[ProcessedTrial], scaler: Scaler, cfg: Config
) -> pd.DataFrame:
    """One row per decision step per trial: confidence, predicted class and, for known ADLs, the true class.

    The true class of a step is the label of the longest window ending at that step.
    """
    longest = max(ens.window_samples)
    rows = []
    for tr in trials:
        x = model_input(tr, scaler, cfg)
        ends = decision_step_ends(len(x), cfg)
        if len(ends) == 0:
            continue
        p_ens, _ = ens.predict_steps(x, ends)
        conf = ood.confidence(p_ens)
        pred = ood.predicted_class(p_ens)
        for e, c, k in zip(ends, conf, pred):
            true = (window_label(tr.physical[e - longest : e], tr.activity_code, cfg)
                    if tr.activity_group == "known_adl" else None)
            rows.append((tr.trial_id, tr.subject_id, tr.age_group, tr.activity_code, tr.activity_group,
                         e / cfg.preprocessing.target_fs, c, ens.classes[k], true))
    return pd.DataFrame(rows, columns=["trial_id", "subject_id", "age_group", "activity_code", "activity_group",
                                       "t_s", "confidence", "predicted_activity", "true_class"])


def _plot_confidence_hist(steps: pd.DataFrame, threshold: float, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(0, 1, 41)
    for group, label, color in (("known_adl", "Known ADLs", "tab:blue"), ("fall", "Simulated falls from SisFall", "tab:red")):
        c = steps.loc[steps["activity_group"] == group, "confidence"]
        ax.hist(c, bins=bins, density=True, alpha=0.55, color=color, label=f"{label} (n={len(c)} steps)")
    ax.axvline(threshold, color="black", ls="--", lw=1, label=f"OOD threshold {threshold}")
    ax.set_xlabel("Ensemble confidence (max softmax)")
    ax.set_ylabel("Density")
    ax.set_title(f"Validation split: DTE confidence per decision step\n{DATA_SOURCE}", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=FIGURE_DPI)
    plt.close(fig)


def _plot_curves(histories: dict[str, list[dict]], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for name, hist in histories.items():
        h = pd.DataFrame(hist)
        axes[0].plot(h["epoch"], h["train_loss"], label=f"{name} train")
        axes[0].plot(h["epoch"], h["val_loss"], ls="--", label=f"{name} val")
        axes[1].plot(h["epoch"], h["val_macro_f1"], label=name)
    axes[0].set(xlabel="Epoch", ylabel="Cross-entropy loss", title="Loss")
    axes[1].set(xlabel="Epoch", ylabel="Macro F1 (validation windows)", title="Validation macro F1")
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=8)
    fig.suptitle("DTE training curves (train/validation splits)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=FIGURE_DPI)
    plt.close(fig)


def run_training(index: pd.DataFrame, splits: dict, cfg: Config) -> dict:
    seed_everything(cfg.seed)
    t0 = time.perf_counter()
    classes = class_names(cfg)

    train_trials = load_processed(index, splits["train"], ["known_adl"], cfg)
    val_known = load_processed(index, splits["val"], ["known_adl"], cfg)
    val_falls = load_processed(index, splits["val"], ["fall"], cfg)
    log.info("Loaded %d train known-ADL, %d val known-ADL, %d val fall trials",
             len(train_trials), len(val_known), len(val_falls))

    scaler = fit_scaler(train_trials, cfg)
    MODEL_DIR.mkdir(exist_ok=True)
    scaler.save(SCALER_PATH)
    assert_scaler_fit_on_train({"fit_subjects": scaler.fit_subjects}, splits)

    models, histories, per_model = [], {}, []
    for i, w in enumerate(cfg.dte.window_lengths_s):
        length = cfg.samples(w)
        xtr, ytr, tr_meta = make_windows(train_trials, length, scaler, cfg)
        assert_no_unknown_in_training(tr_meta, splits, list(cfg.activities.known_adls))
        xva, yva, _ = make_windows(val_known, length, scaler, cfg)
        label_counts = tr_meta["label"].value_counts(normalize=True).round(3).to_dict()
        log.info("Window %.1f s (%d samples): %d train windows, %d val windows; train label shares %s",
                 w, length, len(xtr), len(xva), label_counts)
        model, hist = train_one(xtr, ytr, xva, yva, len(classes), cfg, seed=cfg.seed + i)
        best = max(hist, key=lambda h: h["val_macro_f1"])
        models.append(model)
        histories[f"{w:.1f}s"] = hist
        per_model.append({"model": f"CNN {w:.1f} s", "train_windows": len(xtr), "val_windows": len(xva),
                          "epochs_run": len(hist), "best_epoch": best["epoch"],
                          "val_macro_f1": round(best["val_macro_f1"], 4)})

    window_samples = [cfg.samples(w) for w in cfg.dte.window_lengths_s]
    ens = DeepTimeEnsemble(models, window_samples, classes)

    # Ensemble on validation at the real decision steps (PRD 8.3).
    known_steps = ensemble_step_outputs(ens, val_known, scaler, cfg)
    fall_steps = ensemble_step_outputs(ens, val_falls, scaler, cfg)
    ens_acc = accuracy_score(known_steps["true_class"], known_steps["predicted_activity"])
    ens_f1 = f1_score(known_steps["true_class"], known_steps["predicted_activity"], average="macro", labels=classes)

    thr = cfg.ood.threshold
    steps = pd.concat([known_steps, fall_steps], ignore_index=True)
    steps["is_ood"] = ood.is_ood(steps["confidence"].to_numpy(), thr)
    trial_min = steps.groupby(["trial_id", "activity_group"])["confidence"].min().reset_index()
    trial_any_ood = steps.groupby(["trial_id", "activity_group"])["is_ood"].any().reset_index()
    is_fall_trial = (trial_min["activity_group"] == "fall").astype(int)
    ood_summary = {
        "threshold": thr,
        "val_known_step_ood_rate": float(steps.loc[steps.activity_group == "known_adl", "is_ood"].mean()),
        "val_fall_step_ood_rate": float(steps.loc[steps.activity_group == "fall", "is_ood"].mean()),
        "val_known_trials_with_any_ood_step": float(trial_any_ood.loc[trial_any_ood.activity_group == "known_adl", "is_ood"].mean()),
        "val_fall_trials_with_any_ood_step": float(trial_any_ood.loc[trial_any_ood.activity_group == "fall", "is_ood"].mean()),
        "val_auroc_known_vs_fall_step": float(roc_auc_score(
            (steps["activity_group"] == "fall").astype(int), ood.ood_score(steps["confidence"].to_numpy()))),
        "val_auroc_known_vs_fall_trial_min_conf": float(roc_auc_score(
            is_fall_trial, ood.ood_score(trial_min["confidence"].to_numpy()))),
        "threshold_at_95tpr_val_known": ood.threshold_at_tpr(known_steps["confidence"].to_numpy(), 0.95),
        "median_conf_val_known": float(known_steps["confidence"].median()),
        "median_conf_val_fall": float(fall_steps["confidence"].median()),
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_confidence_hist(steps, thr, FIGURES_DIR / "phase2_val_confidence_hist.png")
    _plot_curves(histories, FIGURES_DIR / "phase2_training_curves.png")

    per_model.append({"model": "Ensemble (decision steps)", "train_windows": None, "val_windows": len(known_steps),
                      "epochs_run": None, "best_epoch": None, "val_macro_f1": round(ens_f1, 4)})
    write_table(pd.DataFrame(per_model), "phase2_dte_val", "DTE validation results (development evidence, not final)",
                f"Validation split, known ADLs only. Label scheme: {cfg.dte.label_scheme}. "
                f"Ensemble step-level accuracy {ens_acc:.4f}.")
    write_table(pd.DataFrame([{k: round(v, 4) if isinstance(v, float) else v for k, v in ood_summary.items()}]).T
                .reset_index().rename(columns={"index": "metric", 0: "value"}),
                "phase2_ood_val", "OOD sanity check on validation (development evidence, not final)",
                "Step-level and trial-level (any OOD step, no event logic) rates at the fixed threshold. "
                "threshold_at_95tpr is a sensitivity note only and is not used for decisions (PRD 8.4).")

    meta = {
        "label_scheme": cfg.dte.label_scheme,
        "class_groups": cfg.activities.class_groups if cfg.dte.label_scheme == "grouped_static" else None,
        "static_thresholds": cfg.dte.static.model_dump() if cfg.dte.label_scheme == "grouped_static" else None,
        "classes": classes,
        "window_lengths_s": list(cfg.dte.window_lengths_s),
        "window_samples": window_samples,
        "channels": list(cfg.preprocessing.channels),
        "dropout": cfg.dte.dropout,
        "target_fs": cfg.preprocessing.target_fs,
        "scaler_path": str(SCALER_PATH),
        "scaler_fit_subjects": scaler.fit_subjects,
        "train_subjects": splits["train"],
        "seed": cfg.seed,
        "git_hash": git_hash(),
        "val_metrics": {"per_model": per_model, "ensemble_step_accuracy": ens_acc,
                        "ensemble_step_macro_f1": ens_f1, "ood": ood_summary},
        "training_seconds": round(time.perf_counter() - t0, 1),
    }
    ens.save(MODEL_DIR, list(cfg.dte.window_lengths_s), meta)
    (MODEL_DIR / "dte_history.json").write_text(pd.Series(histories).to_json(indent=2))
    return meta
