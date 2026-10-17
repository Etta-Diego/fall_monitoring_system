"""Streamlit monitoring dashboard (PRD 12.5).

Run with:  streamlit run app/dashboard.py
Data source: SisFall dataset replay (simulated IoT stream). No physical device.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from fallmon import dashboard_data as dd
from fallmon.config import load_config
from fallmon.data_loader import load_trial
from fallmon.dte import DeepTimeEnsemble
from fallmon.notifier import build_notifier
from fallmon.pipeline import ALERT, HOLD, REJECTED, StreamProcessor, run_config
from fallmon.preprocessing import ALL_CHANNELS, Scaler
from fallmon.splits import load_splits
from fallmon.storage import Storage
from fallmon.stream_simulator import StreamSimulator
from fallmon.verifier import load_params

BANNER = "Data source: SisFall dataset replay (simulated IoT stream). No physical device."
CHART_WINDOW_S = 10.0
UI_REFRESH_S = 0.25  # redraw at most this often (wall clock) during a replay
AM, GM = ALL_CHANNELS.index("Am"), ALL_CHANNELS.index("Gm")
MODE_COLORS = {"baseline": "#d62728", "proposed": "#2ca02c"}

st.set_page_config(page_title="Fall Monitoring (simulated)", layout="wide")


@st.cache_resource
def _runtime():
    cfg = load_config(os.environ.get("FALLMON_CONFIG"))  # optional override, e.g. for tests
    ens, meta = DeepTimeEnsemble.load(Path("models"))
    return cfg, ens, Scaler.load(meta["scaler_path"]), load_params(cfg)


@st.cache_data
def _index_and_splits(processed_dir: str, splits_path: str):
    return pd.read_parquet(Path(processed_dir) / "index.parquet"), load_splits(splits_path)


# ----- Live Replay ----------------------------------------------------------------------------------

def _gauge(conf: float, threshold: float, title: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=conf, number={"valueformat": ".3f"}, title={"text": title, "font": {"size": 14}},
        gauge={"axis": {"range": [0, 1]}, "bar": {"color": "#1f77b4"},
               "steps": [{"range": [0, threshold], "color": "#fde0dd"}],
               "threshold": {"line": {"color": "black", "width": 3}, "value": threshold}}))
    fig.update_layout(height=180, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def _signal_chart(phys: np.ndarray, fs: int, records: dict[str, list[dict]]) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if len(phys):
        t = np.arange(len(phys)) / fs
        keep = t >= t[-1] - CHART_WINDOW_S
        fig.add_trace(go.Scatter(x=t[keep], y=phys[keep, AM], name="Am [g]", line=dict(color="#1f77b4")),
                      secondary_y=False)
        fig.add_trace(go.Scatter(x=t[keep], y=phys[keep, GM], name="Gm [deg/s]",
                                 line=dict(color="#ff7f0e", width=1), opacity=0.6), secondary_y=True)
        t0 = t[keep][0]
        for mode, recs in records.items():
            color = MODE_COLORS[mode]
            for r in recs:
                if r["t_open_s"] >= t0:
                    fig.add_vline(x=r["t_open_s"], line=dict(color=color, dash="dash", width=1))
                if r.get("t_impact_s") is not None and r["t_impact_s"] >= t0:
                    i = int(round(r["t_impact_s"] * fs))
                    fig.add_trace(go.Scatter(x=[r["t_impact_s"]], y=[phys[min(i, len(phys) - 1), AM]], mode="markers",
                                             marker=dict(symbol="triangle-down", size=12, color=color),
                                             name=f"{mode}: impact", showlegend=False))
                if r.get("t_decision_s") is not None and r["t_decision_s"] >= t0 and r["status"] in (ALERT, REJECTED):
                    fig.add_vline(x=r["t_decision_s"], line=dict(color=color, width=2),
                                  annotation_text=f"{mode}: {r['status']}", annotation_position="top left")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.12))
    fig.update_xaxes(title_text="Time in trial [s]")
    fig.update_yaxes(title_text="Am [g]", secondary_y=False)
    fig.update_yaxes(title_text="Gm [deg/s]", secondary_y=True)
    return fig


def _verification_state(proc: StreamProcessor) -> str:
    recs = proc.event_records()
    if not recs:
        return "—"
    last = recs[-1]
    if proc.mode == "baseline":
        return "not used (baseline alerts directly)"
    return {HOLD: "HOLD (verifying...)", ALERT: "VERIFIED", REJECTED: "REJECTED"}.get(last["status"], last["status"])


def page_live_replay(cfg, ens, scaler, params) -> None:
    st.header("Live Replay")
    index, splits = _index_and_splits(str(cfg.dataset.processed_dir), str(cfg.dataset.splits_path))
    unlocked = dd.test_unlocked(cfg)
    trials = dd.replayable_trials(index, splits, unlocked)
    if not unlocked:
        st.caption("Test split locked: only train/validation subjects, known ADLs and falls are offered "
                   "(unknown ADLs and test subjects unlock after the final evaluation).")

    c1, c2, c3, c4 = st.columns([1, 2, 1.4, 1.4])
    subject = c1.selectbox("Subject", sorted(trials["subject_id"].unique()))
    sub = trials[trials["subject_id"] == subject].sort_values(["activity_code", "trial_no"])
    labels = {r.trial_id: f"{r.trial_id} ({r.activity_group.replace('_', ' ')}, {r.duration_s:.0f} s)"
              for r in sub.itertuples()}
    trial_id = c2.selectbox("Trial", list(labels), format_func=labels.get)
    mode = c3.radio("Mode", ["side by side", "baseline", "proposed"], horizontal=True)
    speed = c4.slider("Speed (x real time)", 1, 100, int(cfg.stream.default_speed))
    start = st.button("Start replay", type="primary")

    modes = ["baseline", "proposed"] if mode == "side by side" else [mode]
    status_slots = {m: col.empty() for m, col in zip(modes, st.columns(len(modes)))}
    gauge_slots = {m: col.empty() for m, col in zip(modes, st.columns(len(modes)))}
    chart_slot, alert_slot = st.empty(), st.container()
    if not start:
        st.info("Choose a trial and press **Start replay**.")
        return

    row = index.set_index("trial_id").loc[trial_id]
    trial = load_trial(Path(cfg.dataset.raw_dir) / row["path"], cfg)
    storage = Storage(cfg.logging.db_path)
    notifier = build_notifier(cfg)
    procs = {m: StreamProcessor(m, cfg, ens, scaler, storage, notifier,
                                storage.start_run(m, "dashboard", run_config(cfg, params)), params=params)
             for m in modes}
    latest: dict = {}
    duration = len(trial.data) / trial.fs
    draws = [0]

    def render(t_now: float, done: bool) -> None:
        draws[0] += 1
        for m, p in procs.items():
            d = latest.get(m)
            alerts = sum(r["status"] == ALERT for r in p.event_records())
            with status_slots[m].container():
                st.subheader(m.capitalize())
                st.markdown(
                    f"**Stream:** {'finished' if done else 'streaming'} — {t_now:.1f} s / {duration:.1f} s  \n"
                    f"**Predicted activity:** {d.predicted_activity if d and d.predicted_activity else '—'}  \n"
                    f"**OOD:** {'YES' if d and d.is_ood else 'no'}  \n"
                    f"**Verification:** {_verification_state(p)}  \n"
                    f"**Decision:** {d.status if d else '—'}  \n"
                    f"**Alerts raised:** {alerts}")
            if d is not None and d.predicted_activity:
                gauge_slots[m].plotly_chart(_gauge(d.confidence, p.threshold, "Confidence"),
                                            key=f"gauge-{m}-{draws[0]}")
        first = next(iter(procs.values()))
        chart_slot.plotly_chart(_signal_chart(first.physical_history(), cfg.preprocessing.target_fs,
                                              {m: p.event_records() for m, p in procs.items()}),
                                key=f"chart-{draws[0]}")

    last_draw = 0.0
    for sample in StreamSimulator([trial], speed=float(speed), realtime=True):
        for m, p in procs.items():
            for d in p.push(sample):
                latest[m] = d
                if d.new_alert:
                    alert_slot.error(f"[SIMULATED] {m} alert at {d.t_s:.2f} s in {trial_id}")
        if time.perf_counter() - last_draw > UI_REFRESH_S:
            render(sample.t_s, False)
            last_draw = time.perf_counter()
    for m, p in procs.items():
        for d in p.finish():
            latest[m] = d
            if d.new_alert:
                alert_slot.error(f"[SIMULATED] {m} alert at {d.t_s:.2f} s in {trial_id} (end of trial)")
    render(duration, True)
    storage.close()
    st.success("Replay finished. Runs: " + ", ".join(p.run_id for p in procs.values()))


# ----- Event Details --------------------------------------------------------------------------------

def page_event_details(cfg) -> None:
    st.header("Event Details")
    runs = dd.list_runs(cfg.logging.db_path)
    if runs.empty:
        st.info("No runs logged yet. Start a replay first.")
        return
    run_id = st.selectbox("Run", runs["run_id"],
                          format_func=lambda r: f"{r}  ({runs.set_index('run_id').loc[r, 'split']})")
    ev = dd.events(cfg.logging.db_path, [run_id])
    if ev.empty:
        st.info("This run has no events (no OOD steps).")
        return
    st.dataframe(ev[["event_id", "trial_id", "t_open_s", "t_impact_s", "t_decision_s", "status", "min_confidence"]],
                 hide_index=True)
    event_id = st.selectbox("Event", ev["event_id"])
    e = ev.set_index("event_id").loc[event_id]
    c = st.columns(5)
    c[0].metric("Final decision", e["status"])
    c[1].metric("Min confidence", f"{e['min_confidence']:.3f}")
    c[2].metric("Decision delay", f"{e['decision_delay_s']:.2f} s" if pd.notna(e["decision_delay_s"]) else "—")
    c[3].metric("Latency", f"{e['latency_ms']:.2f} ms" if pd.notna(e["latency_ms"]) else "—")
    c[4].metric("Truncated", "yes" if e["truncated"] else "no")
    st.markdown(f"**Reason:** {e['reason']}")
    st.markdown(f"Opened {e['t_open_s']:.2f} s · impact "
                f"{e['t_impact_s']:.2f} s · decided {e['t_decision_s']:.2f} s" if pd.notna(e["t_impact_s"])
                else f"Opened {e['t_open_s']:.2f} s · decided {e['t_decision_s']:.2f} s (baseline: no verification)")
    rules = dd.rule_table(e, dd.run_params(cfg.logging.db_path, run_id))
    if not rules.empty:
        st.subheader("Verifier features and rules")
        st.dataframe(rules, hide_index=True)


# ----- Logs -------------------------------------------------------------------------------------------

def page_logs(cfg) -> None:
    st.header("Logs")
    runs = dd.list_runs(cfg.logging.db_path)
    if runs.empty:
        st.info("No runs logged yet.")
        return
    c1, c2, c3 = st.columns([3, 1, 2])
    run_ids = c1.multiselect("Runs", runs["run_id"].tolist(), default=runs["run_id"].tolist()[:2])
    modes = c2.multiselect("Mode", ["baseline", "proposed"], default=["baseline", "proposed"])
    subjects = c3.text_input("Subjects (comma separated, blank = all)")
    subj = [s.strip().upper() for s in subjects.split(",") if s.strip()]
    for tab, (label, table) in zip(st.tabs(list(dd.LOG_TABLES)), dd.LOG_TABLES.items()):
        with tab:
            df = dd.log_table(cfg.logging.db_path, table, run_ids, modes, subj)
            st.caption(f"{len(df)} rows (max 5,000 shown)")
            st.dataframe(df, hide_index=True)


# ----- Results ----------------------------------------------------------------------------------------

def page_results() -> None:
    st.header("Results (read-only)")
    tables, figures = dd.results_files()
    st.caption("Tables and figures from results/. Files named phase*/verifier* are validation-split development "
               "evidence; final test-split results appear after the final evaluation.")
    t1, t2 = st.tabs(["Tables", "Figures"])
    with t1:
        choice = st.selectbox("Table", tables, format_func=lambda p: str(p.relative_to("results")))
        if choice:
            st.markdown(Path(choice).read_text())
    with t2:
        for fig in figures:
            st.image(str(fig), caption=str(fig.relative_to("results")))


def main() -> None:
    st.warning(BANNER)
    cfg, ens, scaler, params = _runtime()
    page = st.sidebar.radio("Page", ["Live Replay", "Event Details", "Logs", "Results"])
    st.sidebar.caption(BANNER)
    if page == "Live Replay":
        page_live_replay(cfg, ens, scaler, params)
    elif page == "Event Details":
        page_event_details(cfg)
    elif page == "Logs":
        page_logs(cfg)
    else:
        page_results()


main()
