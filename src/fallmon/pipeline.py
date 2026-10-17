"""Stream decisions in baseline or proposed mode (PRD 10, 12.2).

- `DecisionEngine`: the decision logic (events, alerts, hold and verification). No I/O, no model.
  The live stream and the fast tuning replay both use it, so they cannot drift apart.
- `StreamProcessor`: sample-by-sample preprocessing + DTE inference + engine + logging/notification.

Baseline (Roy et al. 2023 style): an OOD event raises an alert immediately.
Proposed: an OOD event is held, the impact is located, and the alert is raised only if the
post-event temporal verification passes; otherwise the event goes to the unknown-activity log.
Neither class ever sees ground-truth labels; evaluation joins them afterwards by trial_id.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from fallmon import ood
from fallmon.config import Config
from fallmon.data_loader import Trial
from fallmon.dte import DeepTimeEnsemble
from fallmon.events import Event, EventChange, EventTracker
from fallmon.notifier import Alert, MultiNotifier, format_message
from fallmon.preprocessing import Scaler, StreamingPreprocessor, channel_indices
from fallmon.storage import Storage
from fallmon.stream_simulator import Sample, StreamSimulator
from fallmon.verifier import VerificationResult, VerifierParams, compute_features, localise_impact, verify

Mode = Literal["baseline", "proposed"]

# Decision status. PRD 12.2 defines KNOWN, HOLD, ALERT, REJECTED; COOLDOWN marks an OOD step
# suppressed because an alert was raised less than events.cooldown_s ago (D-010).
KNOWN, HOLD, ALERT, REJECTED, COOLDOWN = "KNOWN", "HOLD", "ALERT", "REJECTED", "COOLDOWN"
STATUS_PRIORITY = {ALERT: 4, REJECTED: 3, HOLD: 2, COOLDOWN: 1, KNOWN: 0}
EVAL_CHANNEL = "none (notifications disabled)"

FeatureFn = Callable[[np.ndarray, int, float], tuple[dict, dict]]


@dataclass
class _Pending:
    event_number: int
    t_open: float
    i_impact: int | None = None


@dataclass
class StepResult:
    t: float
    status: str
    event_number: int | None = None
    new_alert: bool = False
    verification: VerificationResult | None = None
    changed_events: list[int] = field(default_factory=list)  # records to (re)write
    alert_events: list[int] = field(default_factory=list)
    rejected_events: list[int] = field(default_factory=list)


class DecisionEngine:
    """Per-trial decision logic, fed once per decision step. Call `reset()` at each trial start."""

    def __init__(self, mode: Mode, cfg: Config, params: VerifierParams | None = None,
                 feature_fn: FeatureFn | None = None):
        if mode not in ("baseline", "proposed"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode == "proposed" and params is None:
            raise ValueError("proposed mode needs verifier parameters")
        self.mode, self.cfg, self.params = mode, cfg, params
        self.fs = cfg.preprocessing.target_fs
        self.search_post = cfg.samples(cfg.verifier.impact_search_post_s)
        self.post = cfg.samples(params.post_window_s) if params else 0
        self.feature_fn = feature_fn or (lambda phys, i, w: compute_features(phys, i, w, cfg))
        self.tracker = EventTracker(cfg.events.merge_gap_s, cfg.events.cooldown_s)
        self.reset()

    def reset(self) -> None:
        self.tracker.reset()
        self.pending: _Pending | None = None
        self.records: dict[int, dict] = {}

    # ----- per step ---------------------------------------------------------------------------

    def step(self, n: int, confidence: float, is_ood: bool, phys_fn: Callable[[], np.ndarray]) -> StepResult:
        """n = processed samples so far (decision time n / fs). phys_fn() returns physical data seen so far."""
        t = n / self.fs
        res = StepResult(t, KNOWN)
        if self.pending is not None:
            self._advance_pending(n, phys_fn, res, final=False)

        change, ev = self.tracker.update(t, is_ood, confidence)
        if change == EventChange.SUPPRESSED:
            self._bump(res, HOLD if self.tracker.blocked else COOLDOWN)
        elif change == EventChange.OPENED:
            self._open(ev, res)
        elif ev is not None:
            rec = self.records[ev.number]
            rec["min_confidence"] = ev.min_confidence
            if change == EventChange.CLOSED:
                rec["t_close_s"] = ev.t_close
                res.changed_events.append(ev.number)
            else:
                res.event_number = ev.number
                self._bump(res, rec["status"])
        return res

    def finish(self, n: int, phys_fn: Callable[[], np.ndarray]) -> StepResult:
        """Trial ended: decide any pending verification with the data available, close open events."""
        res = StepResult(n / self.fs, KNOWN)
        if self.pending is not None:
            self._advance_pending(n, phys_fn, res, final=True)
        ev = self.tracker.close_at_end(res.t)
        if ev is not None:
            self.records[ev.number]["t_close_s"] = ev.t_close
            res.changed_events.append(ev.number)
        return res

    # ----- internals ----------------------------------------------------------------------------

    @staticmethod
    def _bump(res: StepResult, status: str) -> None:
        if STATUS_PRIORITY[status] > STATUS_PRIORITY[res.status]:
            res.status = status

    def _open(self, ev: Event, res: StepResult) -> None:
        rec = {"number": ev.number, "t_open_s": ev.t_open, "t_impact_s": None, "t_decision_s": None,
               "t_close_s": None, "min_confidence": ev.min_confidence, "status": HOLD, "reason": None,
               "features": None, "rules": None, "truncated": 0, "decision_delay_s": None}
        self.records[ev.number] = rec
        res.event_number = ev.number
        res.changed_events.append(ev.number)
        if self.mode == "baseline":
            thr = self.cfg.ood.threshold
            rec.update(status=ALERT, t_decision_s=ev.t_open, decision_delay_s=0.0,
                       reason=(f"confidence {ev.min_confidence:.3f} < threshold {thr:.2f} -> OOD; baseline treats "
                               f"OOD as a probable fall and alerts directly (Roy et al. 2023)"))
            self._alert(rec, res)
        else:
            rec["reason"] = "OOD event: alert held pending post-event temporal verification"
            self.pending = _Pending(ev.number, ev.t_open)
            self.tracker.blocked = True
            self._bump(res, HOLD)

    def _alert(self, rec: dict, res: StepResult) -> None:
        res.new_alert = True
        res.alert_events.append(rec["number"])
        self._bump(res, ALERT)
        self.tracker.start_cooldown(rec["t_decision_s"])

    def _advance_pending(self, n: int, phys_fn, res: StepResult, final: bool) -> None:
        """Locate the impact once data up to t_open + search_post exists; verify once the post window exists."""
        p = self.pending
        i_open = int(round(p.t_open * self.fs))
        if p.i_impact is None:
            if not final and n < i_open + self.search_post + 1:
                return
            p.i_impact = localise_impact(phys_fn(), p.t_open, self.cfg)
        complete = n >= p.i_impact + self.post + 1
        if not final and not complete:
            return
        phys = phys_fn()
        feats, _ = self.feature_fn(phys, p.i_impact, self.params.post_window_s)
        vr = verify(phys, p.i_impact, self.params, self.cfg, truncated=not complete, feats=feats)

        t = n / self.fs
        rec = self.records[p.event_number]
        rec.update(status=ALERT if vr.verified else REJECTED, reason=vr.reason, features=vr.features,
                   rules=vr.rules, t_impact_s=vr.t_impact, t_decision_s=t, truncated=int(vr.truncated),
                   decision_delay_s=t - p.t_open)
        res.verification = vr
        res.event_number = p.event_number
        res.changed_events.append(p.event_number)
        self.pending = None
        self.tracker.blocked = False
        if vr.verified:
            self._alert(rec, res)
        else:
            res.rejected_events.append(p.event_number)
            self._bump(res, REJECTED)
            if self.params.rearm_after_reject:
                ev = self.tracker.end_current(t)
                if ev is not None and ev.number == p.event_number:
                    rec["t_close_s"] = ev.t_close


@dataclass
class Decision:
    t_s: float
    trial_id: str
    subject_id: str
    mode: str
    predicted_activity: str
    confidence: float
    is_ood: bool
    event_id: str | None
    status: str
    latency_ms: float
    new_alert: bool = False  # True only on the step at which an alert was emitted
    verification: VerificationResult | None = None


@dataclass
class _TrialState:
    trial_id: str
    subject_id: str
    prep: StreamingPreprocessor
    norm: list[np.ndarray] = field(default_factory=list)
    physical: list[np.ndarray] = field(default_factory=list)
    n: int = 0  # processed (50 Hz) samples so far
    activity_buf: list[tuple[str, float]] = field(default_factory=list)
    activity_window_start: float | None = None


class StreamProcessor:
    def __init__(self, mode: Mode, cfg: Config, ensemble: DeepTimeEnsemble, scaler: Scaler,
                 storage: Storage | None = None, notifier: MultiNotifier | None = None, run_id: str = "adhoc",
                 params: VerifierParams | None = None, threshold: float | None = None):
        self.mode, self.cfg, self.ens, self.scaler = mode, cfg, ensemble, scaler
        self.storage, self.notifier, self.run_id = storage, notifier, run_id
        self.threshold = cfg.ood.threshold if threshold is None else threshold
        self.engine = DecisionEngine(mode, cfg, params)
        self.fs = cfg.preprocessing.target_fs
        self.ch_idx = channel_indices(cfg)
        self.longest = max(ensemble.window_samples)
        self.step_samples = cfg.samples(cfg.stream.decision_stride_s)
        self.state: _TrialState | None = None

    # ----- public API -------------------------------------------------------------------------

    def push(self, sample: Sample) -> list[Decision]:
        """Feed one raw 200 Hz sample. Returns the decisions produced (one every 0.5 s once 3 s exist)."""
        t_received = time.perf_counter()
        if self.state is None or sample.trial_id != self.state.trial_id:
            self.finish()
            self._start_trial(sample)
        st = self.state
        y = st.prep.push(sample.raw_6ch)
        if y is None:
            return []
        st.physical.append(y)
        st.norm.append(self.scaler.transform(y[self.ch_idx]))
        st.n += 1
        if st.n >= self.longest and (st.n - self.longest) % self.step_samples == 0:
            return [self._decide(t_received)]
        return []

    def finish(self) -> list[Decision]:
        """End of the current trial (or stream): decide pending verifications, close events, flush logs."""
        st = self.state
        if st is None:
            return []
        res = self.engine.finish(st.n, lambda: np.asarray(st.physical))
        self._apply_io(res)
        out = []
        if res.verification is not None:
            out.append(Decision(res.t, st.trial_id, st.subject_id, self.mode, "", float("nan"), False,
                                self._event_id(res.event_number), res.status, 0.0, res.new_alert, res.verification))
        self._flush_activity()
        if self.storage:
            self.storage.commit()
        self.state = None
        return out

    def reset(self) -> None:
        self.finish()
        self.engine.reset()

    # ----- internals ----------------------------------------------------------------------------

    def _start_trial(self, sample: Sample) -> None:
        self.engine.reset()  # never carry events, cooldown or holds across trial boundaries
        self.state = _TrialState(sample.trial_id, sample.subject_id, StreamingPreprocessor(self.cfg))

    def _event_id(self, number: int | None) -> str | None:
        return None if number is None else f"{self.run_id}:{self.state.trial_id}:{number}"

    def _decide(self, t_received: float) -> Decision:
        st = self.state
        x = np.asarray(st.norm[-self.longest:])
        p_ens, _ = self.ens.predict_steps(x, np.array([self.longest]))
        conf = float(ood.confidence(p_ens)[0])
        pred = self.ens.classes[int(ood.predicted_class(p_ens)[0])]
        is_ood = bool(ood.is_ood(np.array([conf]), self.threshold)[0])
        res = self.engine.step(st.n, conf, is_ood, lambda: np.asarray(st.physical))
        latency_ms = (time.perf_counter() - t_received) * 1000  # decision produced; logging I/O excluded

        if not is_ood:
            self._log_known(res.t, pred, conf)
        for number in res.changed_events:
            rec = self.engine.records[number]
            if rec["t_decision_s"] == res.t and rec.get("latency_ms") is None:
                rec["latency_ms"] = latency_ms
        self._apply_io(res)
        return Decision(res.t, st.trial_id, st.subject_id, self.mode, pred, conf, is_ood,
                        self._event_id(res.event_number), res.status, latency_ms, res.new_alert, res.verification)

    def _apply_io(self, res: StepResult) -> None:
        st = self.state
        if any(self.engine.records[n]["t_open_s"] == res.t for n in res.changed_events):
            self._flush_activity(res.t)  # activity before an event is logged before it
        for number in dict.fromkeys(res.changed_events):
            if self.storage:
                self.storage.write_event(self._event_row(number))
        for number in res.alert_events:
            rec = self.engine.records[number]
            title = "Verified fall alert" if self.mode == "proposed" else "Probable fall alert (baseline, unverified)"
            short = (_short_reason(rec) if self.mode == "proposed"
                     else f"low classifier confidence {rec['min_confidence']:.2f} < {self.threshold:.2f}")
            self._emit_alert(number, Alert(title, st.subject_id, st.trial_id, rec["t_decision_s"], short))
        for number in res.rejected_events:
            rec = self.engine.records[number]
            if self.storage:
                self.storage.log_unknown(self.run_id, self._event_id(number), rec["t_decision_s"], st.subject_id,
                                         st.trial_id, rec["reason"])

    def _event_row(self, number: int) -> dict:
        rec, st = self.engine.records[number], self.state
        return {
            "event_id": self._event_id(number), "run_id": self.run_id, "mode": self.mode,
            "subject_id": st.subject_id, "trial_id": st.trial_id,
            **{k: rec[k] for k in ("t_open_s", "t_impact_s", "t_decision_s", "t_close_s", "min_confidence",
                                   "status", "reason", "truncated", "decision_delay_s")},
            "features_json": json.dumps(rec["features"]) if rec["features"] else None,
            "rules_json": json.dumps(rec["rules"]) if rec["rules"] else None,
            "latency_ms": rec.get("latency_ms"),
        }

    def _emit_alert(self, number: int, alert: Alert) -> None:
        message = format_message(alert)
        results = self.notifier.send(alert) if self.notifier else [(EVAL_CHANNEL, False)]
        if self.storage:
            for channel, delivered in results:
                self.storage.log_alert(self.run_id, self._event_id(number), alert.t_s, alert.subject_id,
                                       alert.trial_id, self.mode, channel, delivered, message)

    def _log_known(self, t: float, pred: str, conf: float) -> None:
        """Rate-limited activity log: one row per activity_log_interval_s with the majority activity."""
        st = self.state
        if st.activity_window_start is None:
            st.activity_window_start = t
        st.activity_buf.append((pred, conf))
        if t - st.activity_window_start >= self.cfg.logging.activity_log_interval_s:
            self._flush_activity(t)

    def _flush_activity(self, t: float | None = None) -> None:
        st = self.state
        if not st.activity_buf:
            return
        activity = Counter(p for p, _ in st.activity_buf).most_common(1)[0][0]
        conf = float(np.mean([c for p, c in st.activity_buf if p == activity]))
        if self.storage:
            self.storage.log_activity(self.run_id, t if t is not None else st.n / self.fs, st.subject_id,
                                      st.trial_id, activity, conf)
        st.activity_buf.clear()
        st.activity_window_start = t


def _short_reason(rec: dict) -> str:
    f = rec["features"]
    return (f"impact {f['impact_peak_g']:.1f} g; orientation change {f['orientation_change_deg']:.0f} deg; "
            f"low activity {f['low_activity_s']:.1f} s")


def run_batch(trials: Iterable[Trial], processor: StreamProcessor) -> pd.DataFrame:
    """Replay trials as fast as possible through one processor; one row per decision."""
    rows = []
    current = None

    def _keep(d: Decision) -> None:
        rows.append({k: v for k, v in d.__dict__.items() if k != "verification"})

    for sample in StreamSimulator(trials, realtime=False):
        if current is not None and sample.trial_id != current:
            for d in processor.finish():
                _keep(d)
        current = sample.trial_id
        for d in processor.push(sample):
            _keep(d)
    for d in processor.finish():
        _keep(d)
    return pd.DataFrame(rows)


def summarise_batch(decisions: pd.DataFrame, index: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Trial-level alert rates per activity group, plus step-level OOD and latency figures."""
    groups = index.set_index("trial_id")["activity_group"]
    d = decisions.assign(activity_group=decisions["trial_id"].map(groups))
    per_trial = d.groupby(["trial_id", "activity_group"]).agg(alerts=("new_alert", "sum")).reset_index()
    per_trial["alerted"] = per_trial["alerts"] > 0
    table = (per_trial.groupby("activity_group")
             .agg(trials=("trial_id", "count"), alerted_trials=("alerted", "sum"), alerts=("alerts", "sum"))
             .reset_index())
    table["alerted_rate"] = (table["alerted_trials"] / table["trials"]).round(4)
    steps = d[d["predicted_activity"] != ""]  # exclude end-of-trial verification rows
    stats = {
        "decision_steps": len(steps),
        "step_ood_rate_known_adl": float(steps.loc[steps.activity_group == "known_adl", "is_ood"].mean()),
        "step_ood_rate_fall": float(steps.loc[steps.activity_group == "fall", "is_ood"].mean()),
        "latency_ms_mean": float(steps["latency_ms"].mean()),
        "latency_ms_p95": float(steps["latency_ms"].quantile(0.95)),
        "latency_ms_max": float(steps["latency_ms"].max()),
    }
    return table, stats
