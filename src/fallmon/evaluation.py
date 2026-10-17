"""Final evaluation: experiments E1-E7, demo cases and SUMMARY.md (PRD Section 13, 15).

Everything here runs on a frozen setup (check_frozen) and stamps the frozen hash on every output.
The primary end-to-end results come from real stream runs through StreamProcessor (both modes,
same trials). Secondary results (calibrated threshold, post-window sweep) use the decision-engine
replay, which is checked against the stream runs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, classification_report, confusion_matrix,
                             f1_score, roc_auc_score, roc_curve)
from statsmodels.stats.contingency_tables import mcnemar

from fallmon import ood
from fallmon.config import Config
from fallmon.data_loader import load_trial
from fallmon.dte import DeepTimeEnsemble
from fallmon.pipeline import StreamProcessor, run_batch, run_config
from fallmon.preprocessing import ALL_CHANNELS, Scaler
from fallmon.reporting import DATA_SOURCE, save_figure, write_table
from fallmon.storage import Storage
from fallmon.train import ensemble_step_outputs
from fallmon.tune_verifier import TrialSteps, _FeatureCache, replay
from fallmon.verifier import VerifierParams
from fallmon.windowing import class_names, load_processed

log = logging.getLogger(__name__)

AM, GM = ALL_CHANNELS.index("Am"), ALL_CHANNELS.index("Gm")
MODES = ("baseline", "proposed")
GROUP_LABEL = {"known_adl": "Known ADLs", "unknown_adl": "Unknown ADLs", "fall": "Simulated falls"}
GROUP_COLOR = {"known_adl": "tab:blue", "unknown_adl": "tab:purple", "fall": "tab:red"}
MODE_COLOR = {"baseline": "tab:red", "proposed": "tab:green"}
IMPACT_MATCH_S = 1.0  # an event in a fall trial is "the fall impact" if its impact is within 1 s of the reference
EARLY_ALERT_S = 1.5  # "early alert": first alert more than 1.5 s before the reference impact
CI_METRICS = ("sensitivity", "fpr_known", "fpr_unknown", "precision", "f1")


@dataclass
class EvalContext:
    cfg: Config
    index: pd.DataFrame
    splits: dict
    ens: DeepTimeEnsemble
    scaler: Scaler
    params: VerifierParams
    frozen_hash: str
    split: str  # "test" (final) or "val" (dry run)
    tables_dir: Path
    figures_dir: Path
    summary_path: Path
    demo_path: Path
    db_label: str

    @property
    def groups(self) -> list[str]:
        # Unknown ADLs only ever appear in the final test evaluation (PRD 7.2).
        return ["known_adl", "unknown_adl", "fall"] if self.split == "test" else ["known_adl", "fall"]

    def table(self, df: pd.DataFrame, stem: str, title: str, notes: str = "") -> None:
        split_note = f"Split: {self.split}" + (" (DRY RUN on validation, not a result)" if self.split != "test" else "")
        write_table(df, stem, title, f"{split_note}. {notes}".strip(), self.tables_dir, self.frozen_hash)

    def figure(self, fig, name: str) -> None:
        save_figure(fig, self.figures_dir / name, self.frozen_hash)
        plt.close(fig)


# ----- data collection --------------------------------------------------------------------------

def stream_runs(ctx: EvalContext, rows: pd.DataFrame, threshold: float) -> dict[str, tuple[str, pd.DataFrame]]:
    """Replay every trial through a StreamProcessor per mode (notifications off). Returns run id + decisions."""
    storage = Storage(ctx.cfg.logging.db_path)
    out = {}
    for mode in MODES:
        run_id = storage.start_run(mode, ctx.db_label, run_config(ctx.cfg, ctx.params), ctx.frozen_hash)
        proc = StreamProcessor(mode, ctx.cfg, ctx.ens, ctx.scaler, storage, None, run_id, params=ctx.params,
                               threshold=threshold)
        trials = (load_trial(Path(ctx.cfg.dataset.raw_dir) / p, ctx.cfg) for p in rows["path"])
        t0 = time.perf_counter()
        out[mode] = (run_id, run_batch(trials, proc))
        log.info("stream run %s (%s): %.0f s", mode, run_id, time.perf_counter() - t0)
    storage.close()
    return out


def trial_outcomes(rows: pd.DataFrame, decisions: pd.DataFrame, t_ref: dict[str, float]) -> pd.DataFrame:
    """One row per trial: alert count and first-alert time relative to the reference impact."""
    alerts = decisions[decisions["new_alert"]]
    n = alerts.groupby("trial_id").size()
    first = alerts.groupby("trial_id")["t_s"].min()
    df = rows[["trial_id", "subject_id", "age_group", "activity_code", "activity_group", "duration_s"]].copy()
    df["alerts"] = df["trial_id"].map(n).fillna(0).astype(int)
    df["alerted"] = df["alerts"] > 0
    df["first_alert_s"] = df["trial_id"].map(first)
    df["t_ref_impact_s"] = df["trial_id"].map(t_ref)
    df["first_alert_minus_impact_s"] = df["first_alert_s"] - df["t_ref_impact_s"]
    return df.reset_index(drop=True)


def replay_outcomes(ctx: EvalContext, steps: list[TrialSteps], rows: pd.DataFrame, mode: str, threshold: float,
                    params: VerifierParams | None, t_ref: dict[str, float]) -> pd.DataFrame:
    per_trial, _ = replay(steps, mode, params, ctx.cfg, threshold, _FeatureCache(ctx.cfg) if params else None)
    df = rows[["trial_id", "subject_id", "age_group", "activity_code", "activity_group", "duration_s"]].copy()
    m = per_trial.set_index("trial_id")
    df["alerts"] = df["trial_id"].map(m["alerts"]).fillna(0).astype(int)
    df["alerted"] = df["alerts"] > 0
    df["t_ref_impact_s"] = df["trial_id"].map(t_ref)
    df["first_alert_minus_impact_s"] = df["trial_id"].map(m["first_alert_minus_impact_s"])
    return df


# ----- metrics ------------------------------------------------------------------------------------

def _rates(alerted: np.ndarray, group: np.ndarray) -> dict:
    fall, known, unknown = group == "fall", group == "known_adl", group == "unknown_adl"
    nonfall = ~fall
    tp, fn = int((alerted & fall).sum()), int((~alerted & fall).sum())
    fp, tn = int((alerted & nonfall).sum()), int((~alerted & nonfall).sum())
    sens = tp / (tp + fn) if tp + fn else np.nan
    prec = tp / (tp + fp) if tp + fp else np.nan
    return {
        "sensitivity": sens,
        "specificity": tn / (tn + fp) if tn + fp else np.nan,
        "precision": prec,
        "f1": 2 * prec * sens / (prec + sens) if prec + sens and not np.isnan(prec + sens) else np.nan,
        "accuracy": (tp + tn) / len(alerted) if len(alerted) else np.nan,
        "fpr_known": float(alerted[known].mean()) if known.any() else np.nan,
        "fpr_unknown": float(alerted[unknown].mean()) if unknown.any() else np.nan,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
    }


def end_to_end_metrics(o: pd.DataFrame) -> dict:
    """PRD 13.3 metrics from trial outcomes (alert counts, not just trials, for false alerts per hour)."""
    m = _rates(o["alerted"].to_numpy(), o["activity_group"].to_numpy())
    nonfall = o[o["activity_group"] != "fall"]
    falls = o[(o["activity_group"] == "fall") & o["alerted"]]
    hours = nonfall["duration_s"].sum() / 3600
    delay = falls["first_alert_minus_impact_s"].dropna()
    m.update({
        "false_alerts": int(nonfall["alerts"].sum()),
        "nonfall_hours": hours,
        "false_alerts_per_hour": nonfall["alerts"].sum() / hours if hours else np.nan,
        "delay_mean_s": float(delay.mean()) if len(delay) else np.nan,
        "delay_median_s": float(delay.median()) if len(delay) else np.nan,
        "delay_p95_s": float(delay.quantile(0.95)) if len(delay) else np.nan,
        "early_alert_share": float((delay < -EARLY_ALERT_S).mean()) if len(delay) else np.nan,
    })
    return m


def bootstrap_ci(o: pd.DataFrame, n: int, seed: int) -> dict[str, tuple[float, float]]:
    """95% percentile CIs over trials (resampled with replacement)."""
    rng = np.random.default_rng(seed)
    alerted, group = o["alerted"].to_numpy(), o["activity_group"].to_numpy()
    samples = {k: [] for k in CI_METRICS}
    for _ in range(n):
        idx = rng.integers(0, len(o), len(o))
        r = _rates(alerted[idx], group[idx])
        for k in CI_METRICS:
            samples[k].append(r[k])
    out = {}
    for k, v in samples.items():
        v = np.asarray(v, dtype=float)
        out[k] = ((float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))) if np.isfinite(v).any()
                  else (np.nan, np.nan))  # e.g. no unknown-ADL trials in a validation dry run
    return out


def mcnemar_test(base: pd.DataFrame, prop: pd.DataFrame, group_is_fall: bool) -> dict:
    """Exact McNemar on paired per-trial correctness (falls: alerted is correct; non-falls: not alerted)."""
    b = base.set_index("trial_id")
    p = prop.set_index("trial_id").loc[b.index]
    sel = (b["activity_group"] == "fall") if group_is_fall else (b["activity_group"] != "fall")
    cb = b.loc[sel, "alerted"] if group_is_fall else ~b.loc[sel, "alerted"]
    cp = p.loc[sel, "alerted"] if group_is_fall else ~p.loc[sel, "alerted"]
    table = [[int((cb & cp).sum()), int((cb & ~cp).sum())], [int((~cb & cp).sum()), int((~cb & ~cp).sum())]]
    res = mcnemar(table, exact=True)
    return {"n_trials": int(sel.sum()), "both_correct": table[0][0], "baseline_only_correct": table[0][1],
            "proposed_only_correct": table[1][0], "both_wrong": table[1][1], "p_value": float(res.pvalue)}


# ----- experiments ----------------------------------------------------------------------------------

def e1_classification(ctx: EvalContext, steps: pd.DataFrame) -> dict:
    known = steps[steps["activity_group"] == "known_adl"]
    classes = class_names(ctx.cfg)
    acc = accuracy_score(known["true_class"], known["predicted_activity"])
    macro = f1_score(known["true_class"], known["predicted_activity"], labels=classes, average="macro")
    rep = pd.DataFrame(classification_report(known["true_class"], known["predicted_activity"], labels=classes,
                                             output_dict=True, zero_division=0)).T.reset_index()
    rep = rep.rename(columns={"index": "class"}).round(4)
    ctx.table(rep, "e1_classification", "E1: known-ADL recognition by the DTE (per decision step)",
              f"Accuracy {acc:.4f}, macro F1 {macro:.4f} over {len(known)} decision steps of known-ADL trials. "
              f"Classes: coarse activity groups + static (D-009); true class = label of the 3 s window at each step.")
    cm = confusion_matrix(known["true_class"], known["predicted_activity"], labels=classes, normalize="true")
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(classes)), classes, rotation=45, ha="right")
    ax.set_yticks(range(len(classes)), classes)
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if cm[i, j] > 0.5 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"E1: DTE confusion matrix, known ADLs (row-normalised)\n{DATA_SOURCE}", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    ctx.figure(fig, "e1_confusion_matrix.png")
    return {"accuracy": acc, "macro_f1": macro, "steps": len(known)}


def e2_ood(ctx: EvalContext, steps: pd.DataFrame, thr_cal: float) -> dict:
    thr = ctx.cfg.ood.threshold
    s = steps.assign(score=ood.ood_score(steps["confidence"].to_numpy()))
    trial = s.groupby(["trial_id", "activity_group"])["confidence"].min().reset_index()
    trial["score"] = 1 - trial["confidence"]
    rows, curves = [], {}
    comparisons = [("known vs falls", ["fall"]), ("known vs unknown ADLs", ["unknown_adl"]),
                   ("known vs falls + unknown ADLs", ["fall", "unknown_adl"])]
    for name, pos in comparisons:
        for level, df in (("step", s), ("trial (min confidence)", trial)):
            d = df[df["activity_group"].isin(["known_adl"] + pos)]
            y = d["activity_group"].isin(pos).astype(int)
            if y.nunique() < 2:
                continue
            rows.append({"comparison": name, "level": level, "n_known": int((y == 0).sum()), "n_ood": int(y.sum()),
                         "auroc": roc_auc_score(y, d["score"]), "auprc": average_precision_score(y, d["score"])})
            if level == "step":
                curves[name] = roc_curve(y, d["score"])
    rates = [{"comparison": f"step OOD rate at threshold {t:g}", "level": "step",
              **{GROUP_LABEL[g]: float((s.loc[s.activity_group == g, "confidence"] < t).mean())
                 for g in ctx.groups}} for t in (thr, thr_cal)]
    table = pd.DataFrame(rows).round(4)
    ctx.table(table, "e2_ood", "E2: OOD detection by DTE confidence (threshold-free)",
              "AUROC/AUPRC with OOD (falls and/or unknown ADLs) as the positive class; score = 1 − confidence. "
              "Trial level uses each trial's minimum confidence.")
    ctx.table(pd.DataFrame(rates).round(4), "e2_ood_rates", "E2: share of decision steps flagged OOD",
              f"Primary threshold {thr:g}; calibrated threshold {thr_cal:.4f} (95% TPR on validation known ADLs, D-011).")

    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(0, 1, 41)
    for g in ctx.groups:
        c = s.loc[s.activity_group == g, "confidence"]
        ax.hist(c, bins=bins, density=True, alpha=0.5, color=GROUP_COLOR[g], label=f"{GROUP_LABEL[g]} (n={len(c)})")
    ax.axvline(thr, color="black", ls="--", lw=1, label=f"threshold {thr:g}")
    ax.axvline(thr_cal, color="grey", ls=":", lw=1, label=f"calibrated {thr_cal:.2f}")
    ax.set(xlabel="Ensemble confidence (max softmax)", ylabel="Density")
    ax.set_title(f"E2: DTE confidence per decision step, by group\n{DATA_SOURCE}", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    ctx.figure(fig, "e2_confidence_hist_by_group.png")

    fig, ax = plt.subplots(figsize=(5, 5))
    for name, (fpr, tpr, _) in curves.items():
        auc = table[(table.comparison == name) & (table.level == "step")]["auroc"].iloc[0]
        ax.plot(fpr, tpr, label=f"{name} (AUROC {auc:.3f})")
    ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls=":")
    ax.set(xlabel="False positive rate", ylabel="True positive rate")
    ax.set_title(f"E2: ROC of OOD score per decision step\n{DATA_SOURCE}", fontsize=9)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    ctx.figure(fig, "e2_roc.png")
    return {"table": table}


def _event_type(row, t_ref: dict[str, float]) -> str:
    if row["activity_group"] == "fall":
        near = pd.notna(row["t_impact_s"]) and abs(row["t_impact_s"] - t_ref[row["trial_id"]]) <= IMPACT_MATCH_S
        return "fall impact" if near else "fall trial, other event"
    return GROUP_LABEL[row["activity_group"]]


def e3_verifier(ctx: EvalContext, events: pd.DataFrame, groups: pd.Series, t_ref: dict[str, float]) -> dict:
    ev = events[events["status"].isin(["ALERT", "REJECTED"])].copy()
    ev["activity_group"] = ev["trial_id"].map(groups)
    ev["event_type"] = ev.apply(_event_type, axis=1, t_ref=t_ref)
    ev["verified"] = ev["status"] == "ALERT"
    feats = pd.DataFrame([json.loads(f) for f in ev["features_json"]], index=ev.index)
    rules = pd.DataFrame([json.loads(r) for r in ev["rules_json"]], index=ev.index).astype(float)
    order = [t for t in ("fall impact", "fall trial, other event", "Known ADLs", "Unknown ADLs") if t in set(ev.event_type)]
    summary = (ev.groupby("event_type").agg(events=("event_id", "count"), verified=("verified", "sum"),
                                            truncated=("truncated", "sum"))
               .reindex(order).reset_index())
    summary["verified_rate"] = (summary["verified"] / summary["events"]).round(4)
    rr = rules.assign(event_type=ev["event_type"]).groupby("event_type").mean().reindex(order).round(4).reset_index()
    table = summary.merge(rr, on="event_type")
    fall_imp = ev["event_type"] == "fall impact"
    nonfall = ev["activity_group"] != "fall"
    sub = ev[fall_imp | nonfall]
    cm = confusion_matrix(fall_imp[fall_imp | nonfall], sub["verified"], labels=[True, False])
    ctx.table(table, "e3_verifier", "E3: the verifier on its own (events that reached it, proposed run)",
              f"'fall impact' = event in a fall trial whose located impact is within {IMPACT_MATCH_S:g} s of the "
              f"trial's reference impact (argmax Am). Rule columns = pass rate. Confusion (fall impact vs non-fall "
              f"events): verified/rejected = {cm.tolist()}.")
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.imshow(cm, cmap="Greens")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=12)
    ax.set_xticks([0, 1], ["Verified", "Rejected"])
    ax.set_yticks([0, 1], ["Fall impact", "Non-fall event"])
    ax.set_title(f"E3: verifier decisions on events\n{DATA_SOURCE}", fontsize=9)
    fig.tight_layout()
    ctx.figure(fig, "e3_confusion.png")

    p = ctx.params
    specs = [("impact_peak_g", p.impact_g, "Impact peak [g]"), ("orientation_change_deg", p.orient_deg, "Orientation change [deg]"),
             ("post_am_std_g", p.still_std_g, "Post-impact Am std [g]"), ("low_activity_s", p.rest_s, "Low-activity run [s]")]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6))
    for ax, (col, thr, label) in zip(axes, specs):
        data = [feats.loc[ev.event_type == t, col].dropna() for t in order]
        ax.boxplot(data, showfliers=False)
        ax.set_xticks(range(1, len(order) + 1), [t.replace(", ", ",\n") for t in order], fontsize=7)
        ax.axhline(thr, color="black", ls="--", lw=1)
        ax.set_title(label, fontsize=9)
    fig.suptitle(f"E3: verifier features by event type (dashed = selected threshold)\n{DATA_SOURCE}", fontsize=9)
    fig.tight_layout()
    ctx.figure(fig, "e3_verifier_features_by_group.png")
    return {"table": table, "confusion": cm.tolist(), "events": ev}


def _fmt(v, ci=None, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    s = f"{v:.3f}"
    if ci:
        s += f" [{ci[0]:.3f}, {ci[1]:.3f}]"
    return s


def e4_end_to_end(ctx: EvalContext, outcomes: dict[str, pd.DataFrame], latency: dict[str, pd.Series],
                  secondary: dict[str, pd.DataFrame], thr_cal: float) -> dict:
    n_boot = ctx.cfg.evaluation.bootstrap_resamples
    met = {m: end_to_end_metrics(outcomes[m]) for m in MODES}
    ci = {m: bootstrap_ci(outcomes[m], n_boot, ctx.cfg.seed) for m in MODES}
    fa_b, fa_p = met["baseline"]["false_alerts"], met["proposed"]["false_alerts"]
    reduction = (fa_b - fa_p) / fa_b if fa_b else np.nan
    mc = {"falls": mcnemar_test(outcomes["baseline"], outcomes["proposed"], True),
          "non_falls": mcnemar_test(outcomes["baseline"], outcomes["proposed"], False)}
    rows = []
    labels = [("sensitivity", "Sensitivity (recall)"), ("specificity", "Specificity"), ("precision", "Precision"),
              ("f1", "F1"), ("accuracy", "Accuracy"), ("fpr_known", "FPR known ADLs"),
              ("fpr_unknown", "FPR unknown ADLs"), ("false_alerts", "False alerts (count)"),
              ("false_alerts_per_hour", "False alerts per hour"), ("delay_mean_s", "Decision delay mean [s]"),
              ("delay_median_s", "Decision delay median [s]"), ("delay_p95_s", "Decision delay p95 [s]"),
              ("early_alert_share", f"Falls first alerted > {EARLY_ALERT_S:g} s before impact")]
    for key, label in labels:
        rows.append({"metric": label, **{m: _fmt(met[m][key], ci[m].get(key)) for m in MODES}})
    for m in MODES:
        met[m]["latency_mean_ms"] = float(latency[m].mean())
        met[m]["latency_p95_ms"] = float(latency[m].quantile(0.95))
    rows.append({"metric": "Processing latency mean [ms]", **{m: f"{met[m]['latency_mean_ms']:.3f}" for m in MODES}})
    rows.append({"metric": "Processing latency p95 [ms]", **{m: f"{met[m]['latency_p95_ms']:.3f}" for m in MODES}})
    rows.append({"metric": "False-alert reduction (proposed vs baseline)", "baseline": "", "proposed": _fmt(reduction)})
    rows.append({"metric": "McNemar p, falls (exact)", "baseline": "", "proposed": f"{mc['falls']['p_value']:.4g}"})
    rows.append({"metric": "McNemar p, non-falls (exact)", "baseline": "", "proposed": f"{mc['non_falls']['p_value']:.4g}"})
    table = pd.DataFrame(rows)
    counts = {m: f"TP {met[m]['tp']}, FN {met[m]['fn']}, FP {met[m]['fp']}, TN {met[m]['tn']}" for m in MODES}
    ctx.table(table, "e4_end_to_end", "E4: end-to-end comparison, baseline vs proposed (same trials)",
              f"Threshold {ctx.cfg.ood.threshold:g}. Trial-level: a trial is alerted if at least one ALERT was emitted. "
              f"95% bootstrap CIs in brackets ({n_boot} resamples over trials, seed {ctx.cfg.seed}). "
              f"Decision delay = first alert − reference impact (argmax Am), fall trials; negative = before impact. "
              f"Baseline: {counts['baseline']}. Proposed: {counts['proposed']}. "
              f"McNemar contingency: falls {mc['falls']}, non-falls {mc['non_falls']}.")

    sec_rows = []
    for name, o in secondary.items():
        m = end_to_end_metrics(o)
        sec_rows.append({"system": name, **{k: round(m[k], 4) for k in ("sensitivity", "precision", "f1", "fpr_known",
                                                                         "fpr_unknown", "false_alerts_per_hour",
                                                                         "delay_median_s")}})
    ctx.table(pd.DataFrame(sec_rows), "e4_calibrated_threshold",
              "E4 (secondary, reporting only): both systems at the validation-calibrated threshold",
              f"Threshold {thr_cal:.4f} = 95% TPR on validation known-ADL steps, fixed before the test split was opened "
              f"(D-011). Computed with the decision-engine replay. Primary results use {ctx.cfg.ood.threshold:g}.")

    fig, ax = plt.subplots(figsize=(7, 4))
    keys = [("sensitivity", "Sensitivity"), ("fpr_known", "FPR known"), ("fpr_unknown", "FPR unknown"), ("precision", "Precision")]
    keys = [k for k in keys if not np.isnan(met["baseline"][k[0]])]
    x = np.arange(len(keys))
    for i, m in enumerate(MODES):
        vals = [met[m][k] for k, _ in keys]
        err = np.array([[met[m][k] - ci[m][k][0], ci[m][k][1] - met[m][k]] for k, _ in keys]).T
        ax.bar(x + (i - 0.5) * 0.38, vals, 0.38, yerr=err, capsize=3, color=MODE_COLOR[m], label=m.capitalize())
    ax.set_xticks(x, [lbl for _, lbl in keys])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Rate (trial level)")
    ax.set_title(f"E4: baseline vs proposed (95% bootstrap CI)\n{DATA_SOURCE}", fontsize=9)
    ax.legend()
    fig.tight_layout()
    ctx.figure(fig, "e4_baseline_vs_proposed.png")
    return {"metrics": met, "ci": ci, "mcnemar": mc, "reduction": reduction, "table": table, "secondary": sec_rows}


def e5_post_window(ctx: EvalContext, steps: list[TrialSteps], rows: pd.DataFrame, t_ref: dict) -> pd.DataFrame:
    out = []
    for pw in ctx.cfg.evaluation.sweep_post_window_s:
        o = replay_outcomes(ctx, steps, rows, "proposed", ctx.cfg.ood.threshold, replace(ctx.params, post_window_s=pw), t_ref)
        m = end_to_end_metrics(o)
        out.append({"post_window_s": pw, "sensitivity": m["sensitivity"], "fpr_known": m["fpr_known"],
                    "fpr_unknown": m["fpr_unknown"], "delay_median_s": m["delay_median_s"],
                    "delay_p95_s": m["delay_p95_s"], "selected": pw == ctx.params.post_window_s})
    df = pd.DataFrame(out).round(4)
    ctx.table(df, "e5_sweep", "E5: post-window sensitivity (REPORTING ONLY, not used for model selection)",
              f"Proposed system with every other parameter frozen; only post_window_s varies. "
              f"Post interval starts {ctx.cfg.verifier.post_interval_start_s:g} s after the impact, so at "
              f"post_window_s = {ctx.cfg.verifier.post_interval_start_s:g} s it is empty: the orientation, stillness and rest "
              f"rules cannot pass, so a combination needing them verifies nothing.")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(df["post_window_s"], df["sensitivity"], "o-", label="Sensitivity")
    ax.plot(df["post_window_s"], df["fpr_known"], "s-", label="FPR known")
    if df["fpr_unknown"].notna().any():
        ax.plot(df["post_window_s"], df["fpr_unknown"], "^-", label="FPR unknown")
    ax.set(xlabel="Post window [s]", ylabel="Rate")
    ax2 = ax.twinx()
    ax2.plot(df["post_window_s"], df["delay_median_s"], "k--", label="Median delay [s]")
    ax2.set_ylabel("Median decision delay [s]")
    ax.axvline(ctx.params.post_window_s, color="grey", ls=":", lw=1)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="center right")
    ax.set_title(f"E5: post-window trade-off (reporting only, not used for selection)\n{DATA_SOURCE}", fontsize=9)
    fig.tight_layout()
    ctx.figure(fig, "e5_post_window_tradeoff.png")
    return df


def e6_subgroups(ctx: EvalContext, outcomes: dict[str, pd.DataFrame]) -> dict:
    rows = []
    for age in ("young", "elderly"):
        for m in MODES:
            o = outcomes[m][outcomes[m]["age_group"] == age]
            r = _rates(o["alerted"].to_numpy(), o["activity_group"].to_numpy())
            rows.append({"subgroup": age, "system": m, "subjects": o["subject_id"].nunique(),
                         "fall_trials": int((o.activity_group == "fall").sum()),
                         "known_trials": int((o.activity_group == "known_adl").sum()),
                         "unknown_trials": int((o.activity_group == "unknown_adl").sum()),
                         **{k: r[k] for k in ("sensitivity", "fpr_known", "fpr_unknown", "precision")}})
    age_df = pd.DataFrame(rows).round(4)
    ctx.table(age_df, "e6_subgroups", "E6: results by age group",
              "Elderly falls come from one subject (SE06); elderly subjects other than SE06 never performed D13 or D18 "
              "(see doc/dataset_notes.md).")
    code_rows = []
    for code in ctx.cfg.activities.unknown_adls:
        for m in MODES:
            o = outcomes[m][outcomes[m]["activity_code"] == code]
            if len(o):
                code_rows.append({"activity_code": code, "system": m, "trials": len(o),
                                  "alerted_trials": int(o["alerted"].sum()), "fpr": round(float(o["alerted"].mean()), 4)})
    code_df = pd.DataFrame(code_rows)
    if len(code_df):
        ctx.table(code_df, "e6_unknown_adl_by_code", "E6: false alerts per unknown ADL code",
                  "D10 quick sit (low chair), D11 collapse into chair, D13 lie down quickly, D18 stumble while walking.")
        fig, ax = plt.subplots(figsize=(7, 4))
        codes = list(dict.fromkeys(code_df["activity_code"]))
        x = np.arange(len(codes))
        for i, m in enumerate(MODES):
            vals = [code_df[(code_df.activity_code == c) & (code_df.system == m)]["fpr"].sum() for c in codes]
            ax.bar(x + (i - 0.5) * 0.38, vals, 0.38, color=MODE_COLOR[m], label=m.capitalize())
        ax.set_xticks(x, codes)
        ax.set(ylabel="Share of trials alerted (false alert)", ylim=(0, 1.05))
        ax.set_title(f"E6: false alerts on unseen fall-like ADLs, by code\n{DATA_SOURCE}", fontsize=9)
        ax.legend()
        fig.tight_layout()
        ctx.figure(fig, "e6_unknown_adl_breakdown.png")
    return {"age": age_df, "codes": code_df}


def e7_latency(ctx: EvalContext, latency: dict[str, pd.Series]) -> pd.DataFrame:
    df = pd.DataFrame([{"system": m, "decision_steps": len(v), "mean_ms": v.mean(), "median_ms": v.median(),
                        "p95_ms": v.quantile(0.95), "p99_ms": v.quantile(0.99), "max_ms": v.max()}
                       for m, v in latency.items()]).round(3)
    ctx.table(df, "e7_latency", "E7: processing latency per decision step",
              "Time from receiving the raw sample that completes a decision step to the decision being produced "
              "(preprocessing of that sample + DTE inference + event logic + verification when due); database "
              f"and notification I/O excluded (D-010). Decision interval {ctx.cfg.stream.decision_stride_s:g} s. CPU only.")
    fig, ax = plt.subplots(figsize=(7, 4))
    hi = max(v.quantile(0.995) for v in latency.values())
    bins = np.linspace(0, hi, 60)
    for m, v in latency.items():
        ax.hist(v.clip(upper=hi), bins=bins, alpha=0.55, color=MODE_COLOR[m], label=f"{m} (mean {v.mean():.2f} ms)")
    ax.set(xlabel="Latency per decision step [ms] (clipped at 99.5th percentile)", ylabel="Decision steps")
    ax.set_title(f"E7: processing latency\n{DATA_SOURCE}", fontsize=9)
    ax.legend()
    fig.tight_layout()
    ctx.figure(fig, "e7_latency.png")
    return df


# ----- demo cases (PRD 15) ----------------------------------------------------------------------------

DEMO_RULES = {
    1: "genuine fall: first fall trial (by trial id) where both systems alert and the proposed alert follows a "
       "verified impact within 1 s of the reference impact",
    2: "unseen fall-like ADL: first D10 trial (else any unknown ADL) where the baseline alerts and the proposed does not",
    3: "known ADL: first D01 trial (else any known ADL) where neither system opens an event",
    4: "failure case: first unknown-ADL trial the proposed system still alerts on; else first fall it misses",
}


def select_demo_cases(outcomes: dict[str, pd.DataFrame], events: dict[str, pd.DataFrame], t_ref: dict) -> dict:
    """Deterministic, rule-based choice (no cherry-picking by eye); rules in DEMO_RULES."""
    b = outcomes["baseline"].set_index("trial_id").sort_index()
    p = outcomes["proposed"].set_index("trial_id").sort_index()
    pe = events["proposed"]
    any_event = set(events["baseline"]["trial_id"]) | set(pe["trial_id"])
    cases = {}

    near = {r.trial_id for r in pe.itertuples()
            if r.status == "ALERT" and pd.notna(r.t_impact_s) and abs(r.t_impact_s - t_ref[r.trial_id]) <= IMPACT_MATCH_S}
    c1 = [t for t in b.index if b.loc[t, "activity_group"] == "fall" and b.loc[t, "alerted"] and p.loc[t, "alerted"]
          and t in near]
    unk = [t for t in b.index if b.loc[t, "activity_group"] == "unknown_adl" and b.loc[t, "alerted"] and not p.loc[t, "alerted"]]
    c2 = [t for t in unk if t.startswith("D10")] or unk
    known = [t for t in b.index if b.loc[t, "activity_group"] == "known_adl" and t not in any_event]
    c3 = [t for t in known if t.startswith("D01")] or known
    fail_unk = [t for t in p.index if p.loc[t, "activity_group"] == "unknown_adl" and p.loc[t, "alerted"]]
    fail_fall = [t for t in p.index if p.loc[t, "activity_group"] == "fall" and not p.loc[t, "alerted"]]
    c4 = fail_unk or fail_fall
    for n, lst in ((1, c1), (2, c2), (3, c3), (4, c4)):
        if lst:
            t = lst[0]
            cases[n] = {"trial_id": t, "rule": DEMO_RULES[n], "activity_group": b.loc[t, "activity_group"],
                        "baseline_alerts": int(b.loc[t, "alerts"]), "proposed_alerts": int(p.loc[t, "alerts"])}
        else:
            cases[n] = {"trial_id": None, "rule": DEMO_RULES[n], "note": "no trial matches this rule"}
    return cases


def plot_demo(ctx: EvalContext, case: dict, phys: np.ndarray, events: dict[str, pd.DataFrame], name: str) -> None:
    fs = ctx.cfg.preprocessing.target_fs
    t = np.arange(len(phys)) / fs
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    for ax, m in zip(axes, MODES):
        ax.plot(t, phys[:, AM], color="tab:blue", lw=1)
        ax.set_ylabel("Am [g]")
        ev = events[m][events[m]["trial_id"] == case["trial_id"]]
        for r in ev.itertuples():
            ax.axvline(r.t_open_s, color="orange", ls="--", lw=1)
            if pd.notna(r.t_impact_s):
                i = min(int(round(r.t_impact_s * fs)), len(phys) - 1)
                ax.plot(r.t_impact_s, phys[i, AM], "v", color="black", ms=8)
            if pd.notna(r.t_decision_s):
                color = "red" if r.status == "ALERT" else "green"
                ax.axvline(r.t_decision_s, color=color, lw=2)
                ax.text(r.t_decision_s, ax.get_ylim()[1] * 0.92, f" {r.status}", color=color, fontsize=8)
        ax.set_title(f"{m.capitalize()}: {len(ev)} event(s), {int((ev.status == 'ALERT').sum())} alert(s)", fontsize=9)
    axes[-1].set_xlabel("Time in trial [s]")
    fig.suptitle(f"{case['trial_id']} ({GROUP_LABEL[case['activity_group']]}). Dashed: event opened; ▼ impact; "
                 f"solid: decision\n{DATA_SOURCE}", fontsize=9)
    fig.tight_layout()
    ctx.figure(fig, name)


# ----- summary ----------------------------------------------------------------------------------------

def write_summary(ctx: EvalContext, r: dict) -> None:
    e4 = r["e4"]
    met, ci, mc = e4["metrics"], e4["ci"], e4["mcnemar"]
    lines = [
        "# Final evaluation summary" if ctx.split == "test" else "# DRY RUN summary (validation split, NOT results)",
        "",
        f"Frozen config SHA-256: `{ctx.frozen_hash}`",
        "",
        f"Data source: {DATA_SOURCE}. Falls are simulated falls from SisFall, not real falls of older adults.",
        "",
        f"Split: {ctx.split}. Trials: " + ", ".join(f"{GROUP_LABEL[g]} {int((r['rows'].activity_group == g).sum())}"
                                                   for g in ctx.groups) +
        f". Subjects: {', '.join(sorted(r['rows'].subject_id.unique()))}.",
        f"OOD threshold {ctx.cfg.ood.threshold:g} (both systems). Verifier: {asdict(ctx.params)}.",
        "",
        "## Headline (trial level, 95% bootstrap CI)",
        "",
        "| Metric | Baseline | Proposed |",
        "|---|---|---|",
    ]
    for key, label in (("sensitivity", "Sensitivity"), ("fpr_known", "FPR known ADLs"), ("fpr_unknown", "FPR unknown ADLs"),
                       ("precision", "Precision"), ("f1", "F1")):
        lines.append(f"| {label} | {_fmt(met['baseline'][key], ci['baseline'][key])} | "
                     f"{_fmt(met['proposed'][key], ci['proposed'][key])} |")
    for key, label in (("specificity", "Specificity"), ("accuracy", "Accuracy"), ("false_alerts", "False alerts"),
                       ("false_alerts_per_hour", "False alerts per hour"), ("delay_median_s", "Decision delay median [s]"),
                       ("delay_p95_s", "Decision delay p95 [s]"), ("early_alert_share", "Falls first alerted > 1.5 s before impact"),
                       ("latency_mean_ms", "Latency mean [ms]"), ("latency_p95_ms", "Latency p95 [ms]")):
        lines.append(f"| {label} | {_fmt(met['baseline'][key])} | {_fmt(met['proposed'][key])} |")
    lines += [
        "",
        f"- False-alert reduction: **{_fmt(e4['reduction'])}** ({met['baseline']['false_alerts']} -> "
        f"{met['proposed']['false_alerts']} false alerts).",
        f"- McNemar (exact), falls: p = {mc['falls']['p_value']:.4g} (baseline-only correct "
        f"{mc['falls']['baseline_only_correct']}, proposed-only correct {mc['falls']['proposed_only_correct']}).",
        f"- McNemar (exact), non-falls: p = {mc['non_falls']['p_value']:.4g} (baseline-only correct "
        f"{mc['non_falls']['baseline_only_correct']}, proposed-only correct {mc['non_falls']['proposed_only_correct']}).",
        f"- DTE known-ADL recognition (E1): accuracy {r['e1']['accuracy']:.4f}, macro F1 {r['e1']['macro_f1']:.4f}.",
        f"- Stream vs replay agreement at threshold {ctx.cfg.ood.threshold:g}: {r['agreement']}.",
        "",
        "## Secondary: calibrated threshold (reporting only, D-011)",
        "",
        pd.DataFrame(e4["secondary"]).to_markdown(index=False),
        "",
        "## Failure cases (proposed system)",
        "",
    ]
    p = r["outcomes"]["proposed"]
    unk_alert = p[(p.activity_group == "unknown_adl") & p.alerted]
    falls_missed = p[(p.activity_group == "fall") & ~p.alerted]
    known_alert = p[(p.activity_group == "known_adl") & p.alerted]
    for title, df in (("Unknown-ADL trials still alerted on", unk_alert), ("Known-ADL trials alerted on", known_alert),
                      ("Falls missed", falls_missed)):
        lines.append(f"**{title} ({len(df)}):** " + (", ".join(df["trial_id"]) if len(df) else "none"))
        lines.append("")
    b = r["outcomes"]["baseline"]
    lines.append(f"Baseline falls missed ({int(((b.activity_group == 'fall') & ~b.alerted).sum())}): " +
                 (", ".join(b.loc[(b.activity_group == "fall") & ~b.alerted, "trial_id"]) or "none"))
    lines += ["", "## Demo cases", "", "| Case | Trial | Rule |", "|---|---|---|"]
    for n, c in r["demo"].items():
        lines.append(f"| {n} | {c.get('trial_id') or 'none'} | {c['rule']} |")
    lines += ["", "E5 (post-window sweep) is reporting only and was not used for model selection.", ""]
    ctx.summary_path.write_text("\n".join(lines))


# ----- driver -------------------------------------------------------------------------------------------

def run_evaluation(ctx: EvalContext) -> dict:
    t0 = time.perf_counter()
    cfg = ctx.cfg
    rows = ctx.index[ctx.index["subject_id"].isin(ctx.splits[ctx.split]) &
                     ctx.index["activity_group"].isin(ctx.groups)].sort_values("trial_id").reset_index(drop=True)
    meta = json.loads(Path("models/dte_meta.json").read_text())
    thr_cal = float(meta["val_metrics"]["ood"]["threshold_at_95tpr_val_known"])
    log.info("Evaluating %d trials on split %s", len(rows), ctx.split)

    processed = load_processed(ctx.index, ctx.splits[ctx.split], ctx.groups, cfg)
    fs = cfg.preprocessing.target_fs
    t_ref = {tr.trial_id: float(np.argmax(tr.physical[:, AM]) / fs) for tr in processed}
    phys_by_trial = {tr.trial_id: tr.physical for tr in processed}
    steps = ensemble_step_outputs(ctx.ens, processed, ctx.scaler, cfg)
    by_trial = {tid: g for tid, g in steps.groupby("trial_id")}
    tsteps = [TrialSteps(tr.trial_id, tr.subject_id, tr.activity_group, tr.activity_code, tr.physical,
                         np.round(by_trial[tr.trial_id]["t_s"].to_numpy() * fs).astype(int),
                         by_trial[tr.trial_id]["confidence"].to_numpy(), t_ref[tr.trial_id])
              for tr in processed if tr.trial_id in by_trial]
    log.info("Offline step outputs ready (%.0f s)", time.perf_counter() - t0)

    runs = stream_runs(ctx, rows, cfg.ood.threshold)
    outcomes = {m: trial_outcomes(rows, runs[m][1], t_ref) for m in MODES}
    latency = {m: runs[m][1].loc[runs[m][1]["predicted_activity"] != "", "latency_ms"] for m in MODES}

    # Consistency: streamed confidences == offline confidences; stream outcomes == replay outcomes.
    stream_steps = runs["baseline"][1][runs["baseline"][1]["predicted_activity"] != ""]
    merged = stream_steps.merge(steps, on=["trial_id", "t_s"], suffixes=("_stream", "_offline"))
    max_conf_diff = float((merged["confidence_stream"] - merged["confidence_offline"]).abs().max())
    agree = all((replay_outcomes(ctx, tsteps, rows, m, cfg.ood.threshold, ctx.params if m == "proposed" else None,
                                 t_ref).set_index("trial_id")["alerts"]
                 == outcomes[m].set_index("trial_id")["alerts"]).all() for m in MODES)
    agreement = (f"{'identical' if agree else 'DIFFERENT'} alert counts per trial; "
                 f"max |confidence difference| {max_conf_diff:.2e} over {len(merged)} steps")

    from fallmon.dashboard_data import _connect
    events = {}
    with _connect(cfg.logging.db_path) as con:
        for m in MODES:
            events[m] = pd.read_sql("SELECT * FROM events WHERE run_id = ?", con, params=(runs[m][0],))

    groups = rows.set_index("trial_id")["activity_group"]
    secondary = {
        f"baseline @ {thr_cal:.4f}": replay_outcomes(ctx, tsteps, rows, "baseline", thr_cal, None, t_ref),
        f"proposed @ {thr_cal:.4f}": replay_outcomes(ctx, tsteps, rows, "proposed", thr_cal, ctx.params, t_ref),
    }
    result = {"rows": rows, "outcomes": outcomes, "agreement": agreement, "run_ids": {m: runs[m][0] for m in MODES}}
    result["e1"] = e1_classification(ctx, steps)
    result["e2"] = e2_ood(ctx, steps, thr_cal)
    result["e3"] = e3_verifier(ctx, events["proposed"], groups, t_ref)
    result["e4"] = e4_end_to_end(ctx, outcomes, latency, secondary, thr_cal)
    result["e5"] = e5_post_window(ctx, tsteps, rows, t_ref)
    result["e6"] = e6_subgroups(ctx, outcomes)
    result["e7"] = e7_latency(ctx, latency)
    for m in MODES:
        ctx.table(outcomes[m], f"trial_outcomes_{m}", f"Per-trial outcomes, {m}",
                  f"Run {runs[m][0]}. Ground truth joined after the run.")

    demo = select_demo_cases(outcomes, events, t_ref)
    for n, name in ((1, "demo_case_fall.png"), (2, "demo_case_unknown_adl.png"), (3, "demo_case_known_adl.png"),
                    (4, "demo_case_failure.png")):
        if demo[n].get("trial_id"):
            plot_demo(ctx, demo[n], phys_by_trial[demo[n]["trial_id"]], events, name)
    ctx.demo_path.write_text(json.dumps({"frozen_hash": ctx.frozen_hash, "split": ctx.split,
                                         "cases": {str(k): v for k, v in demo.items()}}, indent=2) + "\n")
    result["demo"] = demo
    write_summary(ctx, result)
    result["seconds"] = round(time.perf_counter() - t0, 1)
    return result
