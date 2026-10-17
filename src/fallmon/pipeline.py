"""StreamProcessor: sample-by-sample decisions in baseline or proposed mode (PRD 12.2).

Baseline (Roy et al. 2023 style): an OOD event raises an alert immediately.
Proposed: an OOD event is held and verified before alerting (added in Phase 4).
The processor never sees ground-truth labels; evaluation joins them afterwards by trial_id.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

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

Mode = Literal["baseline", "proposed"]

# Decision status. PRD 12.2 defines KNOWN, HOLD, ALERT, REJECTED; COOLDOWN marks an OOD step
# that was suppressed because an alert was raised less than events.cooldown_s ago.
KNOWN, HOLD, ALERT, REJECTED, COOLDOWN = "KNOWN", "HOLD", "ALERT", "REJECTED", "COOLDOWN"
EVAL_CHANNEL = "none (notifications disabled)"


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
    verification: Any = None  # VerificationResult in proposed mode (Phase 4)


@dataclass
class _TrialState:
    trial_id: str
    subject_id: str
    prep: StreamingPreprocessor
    norm: list[np.ndarray] = field(default_factory=list)
    physical: list[np.ndarray] = field(default_factory=list)
    n: int = 0  # processed (50 Hz) samples so far
    last_t: float = 0.0
    activity_buf: list[tuple[str, float]] = field(default_factory=list)
    activity_window_start: float | None = None
    event_rows: dict[int, dict] = field(default_factory=dict)


class StreamProcessor:
    def __init__(self, mode: Mode, cfg: Config, ensemble: DeepTimeEnsemble, scaler: Scaler,
                 storage: Storage | None = None, notifier: MultiNotifier | None = None, run_id: str = "adhoc"):
        if mode not in ("baseline", "proposed"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode == "proposed":
            raise NotImplementedError("proposed mode (temporal verification) is built in Phase 4")
        self.mode, self.cfg, self.ens, self.scaler = mode, cfg, ensemble, scaler
        self.storage, self.notifier, self.run_id = storage, notifier, run_id
        self.fs = cfg.preprocessing.target_fs
        self.ch_idx = channel_indices(cfg)
        self.longest = max(ensemble.window_samples)
        self.step_samples = cfg.samples(cfg.stream.decision_stride_s)
        self.tracker = EventTracker(cfg.events.merge_gap_s, cfg.events.cooldown_s)
        self.state: _TrialState | None = None

    # ----- public API -------------------------------------------------------------------------

    def push(self, sample: Sample) -> list[Decision]:
        """Feed one raw 200 Hz sample. Returns the decisions produced (usually none, one per 0.5 s)."""
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

    def finish(self) -> None:
        """End of the current trial (or stream): close any open event, flush logs."""
        st = self.state
        if st is None:
            return
        ev = self.tracker.close_at_end(st.last_t)
        if ev is not None:
            self._on_close(ev)
        self._flush_activity()
        if self.storage:
            self.storage.commit()
        self.state = None

    def reset(self) -> None:
        self.finish()
        self.tracker.reset()

    # ----- internals ----------------------------------------------------------------------------

    def _start_trial(self, sample: Sample) -> None:
        self.tracker.reset()  # never carry events or cooldown across trial boundaries
        self.state = _TrialState(sample.trial_id, sample.subject_id, StreamingPreprocessor(self.cfg))

    def _decide(self, t_received: float) -> Decision:
        st = self.state
        t = st.n / self.fs
        st.last_t = t
        x = np.asarray(st.norm[-self.longest:])
        p_ens, _ = self.ens.predict_steps(x, np.array([self.longest]))
        conf = float(ood.confidence(p_ens)[0])
        pred = self.ens.classes[int(ood.predicted_class(p_ens)[0])]
        is_ood = bool(ood.is_ood(np.array([conf]), self.cfg.ood.threshold)[0])
        change, ev = self.tracker.update(t, is_ood, conf)
        latency_ms = (time.perf_counter() - t_received) * 1000  # decision produced; logging I/O excluded

        decision = Decision(t, st.trial_id, st.subject_id, self.mode, pred, conf, is_ood, None, KNOWN, latency_ms)
        if not is_ood:
            self._log_known(t, pred, conf)
        if change == EventChange.SUPPRESSED:
            decision.status = COOLDOWN
        elif change == EventChange.OPENED:
            self._on_open(ev, decision)
        elif ev is not None:
            row = st.event_rows[ev.number]
            row["min_confidence"] = ev.min_confidence
            decision.event_id, decision.status = row["event_id"], row["status"]
            if change == EventChange.CLOSED:
                self._on_close(ev)
                decision.status = KNOWN
        return decision

    def _on_open(self, ev: Event, decision: Decision) -> None:
        st = self.state
        self._flush_activity(ev.t_open)  # activity before the event is logged before it
        event_id = f"{self.run_id}:{st.trial_id}:{ev.number}"
        thr = self.cfg.ood.threshold
        reason = (f"confidence {ev.min_confidence:.3f} < threshold {thr:.2f} -> OOD; "
                  f"baseline treats OOD as a probable fall and alerts directly (Roy et al. 2023)")
        row = {
            "event_id": event_id, "run_id": self.run_id, "mode": self.mode, "subject_id": st.subject_id,
            "trial_id": st.trial_id, "t_open_s": ev.t_open, "t_impact_s": None, "t_decision_s": ev.t_open,
            "t_close_s": None, "min_confidence": ev.min_confidence, "status": ALERT, "reason": reason,
            "features_json": None, "rules_json": None, "truncated": 0, "decision_delay_s": 0.0,
            "latency_ms": decision.latency_ms,
        }
        st.event_rows[ev.number] = row
        decision.event_id, decision.status, decision.new_alert = event_id, ALERT, True
        if self.storage:
            self.storage.write_event(row)
        self._emit_alert(row, Alert("Probable fall alert (baseline, unverified)", st.subject_id, st.trial_id,
                                    ev.t_open, f"low classifier confidence {ev.min_confidence:.2f} < {thr:.2f}"))
        self.tracker.start_cooldown(ev.t_open)

    def _on_close(self, ev: Event) -> None:
        row = self.state.event_rows[ev.number]
        row["t_close_s"], row["min_confidence"] = ev.t_close, ev.min_confidence
        if self.storage:
            self.storage.write_event(row)

    def _emit_alert(self, row: dict, alert: Alert) -> None:
        message = format_message(alert)
        results = self.notifier.send(alert) if self.notifier else [(EVAL_CHANNEL, False)]
        if self.storage:
            for channel, delivered in results:
                self.storage.log_alert(self.run_id, row["event_id"], alert.t_s, alert.subject_id, alert.trial_id,
                                       self.mode, channel, delivered, message)

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
            self.storage.log_activity(self.run_id, t if t is not None else st.last_t, st.subject_id, st.trial_id,
                                      activity, conf)
        st.activity_buf.clear()
        st.activity_window_start = t


def run_batch(trials: Iterable[Trial], processor: StreamProcessor) -> pd.DataFrame:
    """Replay trials as fast as possible through one processor; one row per decision step."""
    rows = []
    for sample in StreamSimulator(trials, realtime=False):
        for d in processor.push(sample):
            rows.append({k: v for k, v in d.__dict__.items() if k != "verification"})
    processor.finish()
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
    stats = {
        "decision_steps": len(d),
        "step_ood_rate_known_adl": float(d.loc[d.activity_group == "known_adl", "is_ood"].mean()),
        "step_ood_rate_fall": float(d.loc[d.activity_group == "fall", "is_ood"].mean()),
        "latency_ms_mean": float(d["latency_ms"].mean()),
        "latency_ms_p95": float(d["latency_ms"].quantile(0.95)),
        "latency_ms_max": float(d["latency_ms"].max()),
    }
    return table, stats
