# Phase 3 report: Event logic and real-time stream

- Date completed: 2026-10-17
- Git commit: (uncommitted at time of writing; base commit d42a0d7)
- PRD sections: 10, 11 (test lock, interim), 12.1–12.4, 14 (Phase 3)

## What was built
- `src/fallmon/events.py`: `EventTracker`, which turns per-step OOD flags into events (open, merge, close, cooldown).
- `src/fallmon/stream_simulator.py`: `StreamSimulator`, which replays trials sample by sample at 200 Hz, paced to the wall clock × speed or as fast as possible.
- `src/fallmon/pipeline.py`: `StreamProcessor` (baseline mode; proposed mode is Phase 4), `run_batch`, `summarise_batch`.
- `src/fallmon/storage.py`: SQLite schema and writers (`runs`, `activity_log`, `events`, `unknown_activity_log`, `alert_log`).
- `src/fallmon/notifier.py`: `[SIMULATED]` message template, `ConsoleNotifier`, `MultiNotifier` (failures logged, never raised).
- `src/fallmon/guards.py`: `assert_not_test` (interim test lock until `fallmon freeze` exists in Phase 5).
- CLI: `fallmon stream --trial ID --mode baseline --speed N [--fast]`, `fallmon batch --split val --mode baseline`.

## How it works (for the thesis)
- **Simulated IoT stream.** Each SisFall trial is replayed one raw 200 Hz sample at a time (already converted to g and °/s). Trials are chained back to back with no invented data; when the trial id changes, the processor resets all filter, buffer and event state.
- **Stream processor, per sample:** causal low-pass filter (state carried between samples), keep every 4th sample (50 Hz), compute Am/Gm, z-score. Every 0.5 s once 3 s of data exist, the three CNNs each take the latest window of their length, softmax outputs are averaged, and confidence = max probability. Confidence < 0.9 marks the step OOD.
- **Event logic (PRD 10):** an event opens at the first OOD step when none is open and no cooldown is active; OOD steps no more than 1.0 s after the previous OOD step extend it; it closes once 1.0 s passes with no OOD step; an alert starts a 10 s cooldown during which no new event can open. All state resets at trial boundaries.
- **Baseline mode:** an event opening raises an ALERT immediately, as in Roy et al. (2023), with reason text `confidence 0.669 < threshold 0.90 -> OOD; baseline treats OOD as a probable fall and alerts directly`.
- **Logging:** each event is one row in `events` (open, decision and close times, minimum confidence, status, reason, latency). Each alert is a row in `alert_log`, one per notification channel. Confident steps are summarised in `activity_log`, one row per 2 s with the majority activity. Batch runs log alerts with channel `none (notifications disabled)`.
- **Processing latency:** for each decision step, the time from receiving the raw sample that completes the step to the decision being produced (model inference + event logic), measured with `time.perf_counter()`. Database and notification I/O are excluded.

## Acceptance checks
| Check (PRD 14, Phase 3) | Result | Evidence |
|---|---|---|
| `fallmon stream --trial F05_SA01_R01 --mode baseline --speed 20` prints decisions and writes DB rows | pass | 25 decisions printed; one event (open 7.0 s, close 10.5 s, min confidence 0.445, ALERT); one console alert with `[SIMULATED]`; activity rows written |
| `test_events.py` covers merge, close, cooldown | pass | 9 tests (open, merge within gap, close after gap, reopen, min confidence, cooldown suppression, extend during cooldown, reset, close at trial end) |
| Batch mode over validation runs end to end and reports per-step latency | pass | `results/tables/phase3_batch_val_baseline.md`: 21,748 steps, mean 1.75 ms, p95 2.59 ms |

## Tests
- `pytest`: **51 passed**.
- `test_events.py` (9): see above.
- `test_pipeline.py` (7): no events when always confident; first decision at 3.0 s, then every 0.5 s; one alert per event; cooldown blocks a second alert and allows one after 10 s; state resets at trial boundaries; **streamed confidences equal offline batch inference** (to 1e-5); database rows (event reason, `[SIMULATED]` alert message, activity log); simulator emits every sample in order.
- `test_guards.py` (+1): test lock refuses test-split subjects.

## Results produced
Validation split, baseline mode, run `20261017T055454-baseline-765f17` (development evidence, not final). Known ADLs and falls only; unknown ADLs excluded.

| activity_group | trials | alerted trials | alerts | alerted rate |
|---|---|---|---|---|
| fall | 300 | 300 | 320 | 1.0000 |
| known_adl | 381 | 370 | 496 | 0.9711 |

- **Consistency check:** step OOD rates 0.3649 (known) and 0.4729 (falls), identical to the offline Phase 2 numbers (X-003). The sample-by-sample stream and offline evaluation agree.
- **Latency per decision step:** mean 1.746 ms, p95 2.589 ms, max 61.3 ms (single outlier, likely first call / garbage collection), over 21,748 steps on CPU. Well within the 0.5 s decision interval.
- **Baseline alert timing on falls** (ad hoc check on the same run): median first-alert time is 1.23 s **before** the impact (Am peak); 5th–95th percentile −4.59 s to +0.96 s. **44.0% of fall trials get their first alert more than 1.5 s before the impact**, during the activity before the fall. 20 of 300 fall trials got two alerts.

## Decisions and deviations
- D-010 Phase 3 implementation details (COOLDOWN status, `new_alert` flag, `t_close_s` column, latency definition, activity-log flush on event open, interim test lock).

## Problems and limitations found
- **Early baseline alerts on falls** (see Results). Two consequences, recorded in `limitations.md`:
  1. Trial-level sensitivity ("any alert in a fall trial") counts alerts raised during pre-fall walking as detections, which flatters the baseline. Phase 6 should also report alert timing relative to impact.
  2. **Phase 4 design risk:** in the proposed mode, an event that opens early and stays open through the impact is verified only once, at the start, so the verifier's impact search (−1.5 s / +1.0 s around the event start, PRD 9.2) can miss the real impact. To be handled in Phase 4 and decided on validation data.
- Batch replay uses ~3.5 CPU cores for single-window inference (torch default threads); harmless, could be pinned to 1 thread for speed.

## Thesis pointers
- Chapter 4.7 (event logic, stream, storage): this report; SQLite schema in `src/fallmon/storage.py`.
- Chapter 4.10 E7 (latency) will use the Phase 6 test run; the validation figures here are development evidence.
