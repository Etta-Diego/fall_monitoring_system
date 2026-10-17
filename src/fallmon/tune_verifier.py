"""Grid search of the verifier on validation known ADLs and falls only (PRD 9.5).

The DTE confidences do not depend on the verifier, so they are computed once per trial; each grid
configuration then replays only the DecisionEngine (the same code the live stream uses).
Objective: minimise the validation known-ADL false-alert rate subject to validation fall recall
>= verifier.min_fall_recall. Ties: shorter post window, simpler combine mode, no re-arm,
higher recall, then grid order.
"""

from __future__ import annotations

import itertools
import logging
import multiprocessing as mp
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fallmon.config import Config
from fallmon.dte import DeepTimeEnsemble
from fallmon.guards import assert_verifier_tuned_without_test_or_unknown
from fallmon.pipeline import DecisionEngine
from fallmon.preprocessing import ALL_CHANNELS, Scaler
from fallmon.reporting import DATA_SOURCE, FIGURE_DPI, FIGURES_DIR, TABLES_DIR, write_table
from fallmon.train import ensemble_step_outputs
from fallmon.utils import git_hash
from fallmon.verifier import COMBINE_SIMPLICITY, VerifierParams, compute_features
from fallmon.windowing import load_processed

log = logging.getLogger(__name__)

TUNING_GROUPS = ["known_adl", "fall"]  # never unknown ADLs (PRD 7.2)
VERIFIER_CONFIG_PATH = Path("models/verifier_config.json")
AM = ALL_CHANNELS.index("Am")


@dataclass
class TrialSteps:
    trial_id: str
    subject_id: str
    activity_group: str
    activity_code: str
    phys: np.ndarray  # (m, 8) physical, 50 Hz
    step_n: np.ndarray  # processed-sample count at each decision step
    conf: np.ndarray  # ensemble confidence at each step
    t_impact_ref: float  # argmax Am over the whole trial (PRD 13.1); delay reporting only


def grid_params(cfg: Config) -> list[VerifierParams]:
    g = cfg.verifier.grid
    out = []
    for imp, ori, sti, rest, comb, k, pw, rearm in itertools.product(
            g.impact_g, g.orient_deg, g.still_std_g, g.rest_s, g.combine, g.k, g.post_window_s, g.rearm_after_reject):
        if comb != "impact_and_k_of_3" and k != g.k[0]:
            continue  # k only matters for k-of-3
        out.append(VerifierParams(imp, ori, sti, rest, comb, k if comb == "impact_and_k_of_3" else cfg.verifier.k,
                                  pw, rearm))
    return out


def prepare_trials(index: pd.DataFrame, splits: dict, ens: DeepTimeEnsemble, scaler: Scaler,
                   cfg: Config) -> list[TrialSteps]:
    trials = load_processed(index, splits["val"], TUNING_GROUPS, cfg)
    steps = ensemble_step_outputs(ens, trials, scaler, cfg)
    by_trial = {tid: g for tid, g in steps.groupby("trial_id")}
    fs = cfg.preprocessing.target_fs
    out = []
    for tr in trials:
        g = by_trial.get(tr.trial_id)
        if g is None:
            continue
        out.append(TrialSteps(tr.trial_id, tr.subject_id, tr.activity_group, tr.activity_code, tr.physical,
                              np.round(g["t_s"].to_numpy() * fs).astype(int), g["confidence"].to_numpy(),
                              float(np.argmax(tr.physical[:, AM]) / fs)))
    return out


class _FeatureCache:
    """Memoise verifier features per (trial, impact index, post window, samples used)."""

    def __init__(self, cfg: Config):
        self.cfg, self.trial_id, self.store = cfg, None, {}

    def __call__(self, phys: np.ndarray, i_impact: int, post_window_s: float):
        used = min(len(phys), i_impact + self.cfg.samples(post_window_s) + 1)
        key = (self.trial_id, i_impact, post_window_s, used)
        if key not in self.store:
            self.store[key] = compute_features(phys[:used], i_impact, post_window_s, self.cfg)
        return self.store[key]


def replay(trials: list[TrialSteps], mode: str, params: VerifierParams | None, cfg: Config, threshold: float,
           cache: _FeatureCache | None = None, collect_events: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """Run the decision engine over precomputed confidences. One row per trial (+ verified-event records)."""
    engine = DecisionEngine(mode, cfg, params, feature_fn=cache)
    rows, events = [], []
    for tr in trials:
        if cache is not None:
            cache.trial_id = tr.trial_id
        engine.reset()
        alert_times, verifications, truncated = [], 0, 0
        results = []
        for n, c in zip(tr.step_n, tr.conf):
            results.append(engine.step(int(n), float(c), bool(c < threshold), lambda n=n: tr.phys[:n]))
        results.append(engine.finish(len(tr.phys), lambda: tr.phys))
        for r in results:
            if r.new_alert:
                alert_times.append(r.t)
            if r.verification is not None:
                verifications += 1
                truncated += int(r.verification.truncated)
                if collect_events:
                    events.append({"trial_id": tr.trial_id, "activity_group": tr.activity_group,
                                   "activity_code": tr.activity_code, "verified": r.verification.verified,
                                   "truncated": r.verification.truncated, "t_impact": r.verification.t_impact,
                                   **r.verification.features})
        first = alert_times[0] if alert_times else np.nan
        rows.append({"trial_id": tr.trial_id, "activity_group": tr.activity_group, "alerts": len(alert_times),
                     "alerted": bool(alert_times), "first_alert_minus_impact_s": first - tr.t_impact_ref,
                     "verifications": verifications, "truncated": truncated})
    return pd.DataFrame(rows), events


def summarise(per_trial: pd.DataFrame) -> dict:
    known = per_trial[per_trial.activity_group == "known_adl"]
    falls = per_trial[per_trial.activity_group == "fall"]
    delay = falls.loc[falls.alerted, "first_alert_minus_impact_s"]
    return {
        "fa_rate_known": float(known.alerted.mean()),
        "fall_recall": float(falls.alerted.mean()),
        "known_alerts": int(known.alerts.sum()),
        "fall_alerts": int(falls.alerts.sum()),
        "verifications": int(per_trial.verifications.sum()),
        "truncated": int(per_trial.truncated.sum()),
        "median_first_alert_minus_impact_s": float(delay.median()) if len(delay) else np.nan,
        "p95_first_alert_minus_impact_s": float(delay.quantile(0.95)) if len(delay) else np.nan,
        "falls_first_alert_before_impact_gt_1_5s": float((delay < -1.5).mean()) if len(delay) else np.nan,
    }


# ----- parallel grid evaluation (worker globals set by fork) ------------------------------------

_W: dict = {}


def _init_worker(trials, cfg, threshold):
    _W.update(trials=trials, cfg=cfg, threshold=threshold, cache=_FeatureCache(cfg))


def _eval(params: VerifierParams) -> dict:
    per_trial, _ = replay(_W["trials"], "proposed", params, _W["cfg"], _W["threshold"], _W["cache"])
    return {**asdict(params), **summarise(per_trial)}


def select(grid: pd.DataFrame, min_recall: float) -> tuple[pd.Series, str]:
    g = grid.assign(_simple=grid["combine"].map(COMBINE_SIMPLICITY.index), _order=np.arange(len(grid)))
    feasible = g[g["fall_recall"] >= min_recall]
    if len(feasible):
        best = feasible.sort_values(["fa_rate_known", "post_window_s", "_simple", "rearm_after_reject",
                                     "fall_recall", "_order"], ascending=[True, True, True, True, False, True]).iloc[0]
        note = (f"{len(feasible)} of {len(g)} configurations meet fall recall >= {min_recall}; "
                f"selected the lowest known-ADL false-alert rate (ties: shorter post window, simpler combine, "
                f"no re-arm, higher recall, grid order).")
    else:
        best = g.sort_values(["fall_recall", "fa_rate_known", "post_window_s", "_simple", "rearm_after_reject",
                              "_order"], ascending=[False, True, True, True, True, True]).iloc[0]
        note = (f"NO configuration meets fall recall >= {min_recall} (best {g['fall_recall'].max():.4f}). "
                f"Selected the highest-recall configuration instead (PRD 9.5); the constraint was not relaxed.")
    return best.drop(["_simple", "_order"]), note


def _plot_features(events: pd.DataFrame, params: VerifierParams, out: Path) -> None:
    specs = [("impact_peak_g", params.impact_g, "Impact peak [g]"),
             ("orientation_change_deg", params.orient_deg, "Orientation change [deg]"),
             ("post_am_std_g", params.still_std_g, "Post-impact Am std [g]"),
             ("low_activity_s", params.rest_s, "Longest low-activity run [s]")]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4))
    for ax, (col, thr, label) in zip(axes, specs):
        data = [events.loc[events.activity_group == g, col].dropna() for g in ("known_adl", "fall")]
        ax.boxplot(data, labels=["Known ADL", "Fall"], showfliers=False)
        ax.axhline(thr, color="black", ls="--", lw=1)
        ax.set_title(label, fontsize=9)
    fig.suptitle(f"Validation split: features of events reaching the verifier (selected config; dashed = threshold)\n"
                 f"{DATA_SOURCE}", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=FIGURE_DPI)
    plt.close(fig)


def run_tuning(index: pd.DataFrame, splits: dict, ens: DeepTimeEnsemble, scaler: Scaler, cfg: Config,
               workers: int = 0) -> dict:
    t0 = time.perf_counter()
    tuning_index = index[index["subject_id"].isin(splits["val"]) & index["activity_group"].isin(TUNING_GROUPS)]
    assert_verifier_tuned_without_test_or_unknown(tuning_index, splits)

    trials = prepare_trials(index, splits, ens, scaler, cfg)
    assert_verifier_tuned_without_test_or_unknown(
        pd.DataFrame({"subject_id": [t.subject_id for t in trials], "activity_group": [t.activity_group for t in trials]}),
        splits)
    thr = cfg.ood.threshold
    log.info("Prepared %d validation trials in %.0f s", len(trials), time.perf_counter() - t0)

    params_list = grid_params(cfg)
    workers = workers or min(8, mp.cpu_count())
    log.info("Evaluating %d configurations on %d workers", len(params_list), workers)
    with mp.get_context("fork").Pool(workers, initializer=_init_worker, initargs=(trials, cfg, thr)) as pool:
        grid = pd.DataFrame(pool.map(_eval, params_list, chunksize=8))
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    grid.to_csv(TABLES_DIR / "verifier_grid_val.csv", index=False)

    best, note = select(grid, cfg.verifier.min_fall_recall)
    chosen = VerifierParams(**{k: (bool(best[k]) if k == "rearm_after_reject" else
                                   int(best[k]) if k == "k" else
                                   str(best[k]) if k == "combine" else float(best[k]))
                               for k in VerifierParams.__dataclass_fields__})

    base_trials, _ = replay(trials, "baseline", None, cfg, thr)
    base = summarise(base_trials)
    prop_trials, events = replay(trials, "proposed", chosen, cfg, thr, _FeatureCache(cfg), collect_events=True)
    prop = summarise(prop_trials)
    events = pd.DataFrame(events)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_features(events, chosen, FIGURES_DIR / "phase4_val_verifier_features.png")

    rule_rates = {}
    if len(events):
        from fallmon.verifier import apply_rules
        rr = pd.DataFrame([apply_rules(e, chosen)[1] for e in events.to_dict("records")])
        rr["activity_group"] = events["activity_group"].to_numpy()
        rule_rates = rr.groupby("activity_group").mean().round(4).to_dict(orient="index")

    meta = {
        "selected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_hash": git_hash(),
        "selection_note": note,
        "objective": f"min val known-ADL false-alert rate s.t. val fall recall >= {cfg.verifier.min_fall_recall}",
        "tuning_split": "val",
        "tuning_groups": TUNING_GROUPS,
        "tuning_subjects": sorted({t.subject_id for t in trials}),
        "n_trials": {g: int(sum(t.activity_group == g for t in trials)) for g in TUNING_GROUPS},
        "ood_threshold": thr,
        "grid_size": len(grid),
        "val_proposed": prop,
        "val_baseline": base,
        "val_rule_pass_rates": rule_rates,
        "seconds": round(time.perf_counter() - t0, 1),
    }
    chosen.save(VERIFIER_CONFIG_PATH, meta)

    rows = [{"setting": k, "value": v} for k, v in asdict(chosen).items()]
    rows += [{"setting": f"val proposed: {k}", "value": round(v, 4) if isinstance(v, float) else v} for k, v in prop.items()]
    rows += [{"setting": f"val baseline: {k}", "value": round(v, 4) if isinstance(v, float) else v} for k, v in base.items()]
    write_table(pd.DataFrame(rows), "verifier_selected_config",
                "Selected verifier configuration (validation split, development evidence)",
                note + f" Grid of {len(grid)} configurations; full results in verifier_grid_val.csv.")
    top = grid.sort_values(["fall_recall", "fa_rate_known"], ascending=[False, True])
    top = top[top.fall_recall >= cfg.verifier.min_fall_recall].sort_values("fa_rate_known").head(15)
    write_table(top.round(4), "verifier_grid_val_top", "Best feasible verifier configurations (validation)",
                f"Feasible = val fall recall >= {cfg.verifier.min_fall_recall}. Sorted by known-ADL false-alert rate.")
    return {"params": asdict(chosen), **meta}
