# Phase 5 report: Dashboard and freeze

- Date completed: 2026-10-17
- Git commit: (uncommitted at time of writing; base commit 3845497)
- PRD sections: 11.5, 12.4, 12.5, 14 (Phase 5)
- Scope change: email and Telegram notifiers removed (D-014). Console notifications only; alerts are stored in the alert log and shown on the dashboard.

## What was built
- `app/dashboard.py`: Streamlit dashboard with four pages (Live Replay, Event Details, Logs, Results) and the banner "Data source: SisFall dataset replay (simulated IoT stream). No physical device." on every page.
- `src/fallmon/dashboard_data.py`: read-only database queries, trial availability under the test lock, feature/rule/threshold table, results file listing (unit-testable without Streamlit).
- `src/fallmon/guards.py`: `freeze_payload`, `write_freeze`, `check_frozen` (test lock, PRD 11.5).
- `src/fallmon/pipeline.py`: `physical_history()` and `event_records()` accessors for display; `run_config()` stores the verifier parameters with every run.
- CLI: `fallmon freeze [--force]`.

## How it works (for the thesis)
**Dashboard pages**
1. **Live Replay:** choose subject, trial, mode (baseline, proposed, or side by side) and speed (1–100× real time). The selected trial is streamed sample by sample through one `StreamProcessor` per mode (side by side = two processors on the same sample stream). The page shows, per mode: stream status and time, predicted activity, a confidence gauge with the 0.9 threshold, OOD flag, verification state (HOLD / VERIFIED / REJECTED), the latest decision and the number of alerts; and a rolling 10 s chart of Am and Gm with dashed lines at event opening, triangles at the located impact and solid lines at the final decision, coloured per mode. Each replay is logged as a run in SQLite (split `dashboard`).
2. **Event Details:** pick a run and an event; shows final decision, minimum confidence, decision delay, latency, truncation, the full reason text, and a table of every verifier feature with its rule, threshold and PASS/FAIL.
3. **Logs:** activity log, unknown-activity log and alert log, filtered by run, mode and subject.
4. **Results:** read-only view of every table and figure in `results/`.

**Test lock in the dashboard.** Until the final evaluation is done (valid frozen config and `results/SUMMARY.md` exists), Live Replay offers only train and validation subjects, and only known ADLs and falls. Unknown ADLs stay hidden so nobody can tune by eye on them.

**Freeze (PRD 11.5).** `fallmon freeze` writes `results/frozen_config.yaml` containing the merged configuration, the selected verifier parameters, and the SHA-256 of every file that determines test results (`models/dte_w*.pt`, `dte_meta.json`, `scaler.json`, `verifier_config.json`, `data/splits.json`), plus the SHA-256 of the YAML itself in `results/frozen_config.sha256`. `check_frozen` refuses (raises `TestLockError`) if the frozen file is missing, has been edited, or if any config value or file hash differs now. Phase 6 will call it before opening the test split and print the hash in every output.

## Acceptance checks
| Check (PRD 14, Phase 5, after D-014) | Result | Evidence |
|---|---|---|
| Dashboard runs with `streamlit run app/dashboard.py`; side-by-side mode works on a validation trial | pass | Server started headless and answered the health check. `tests/test_dashboard.py::test_dashboard_app_side_by_side_replay` runs the real app with Streamlit's `AppTest`: all four pages load without errors, only train/val subjects are offered, a side-by-side replay on a validation subject at 100× completes and logs one baseline and one proposed run. **Not checked visually by the agent** (headless screenshot only captured the loading skeleton). |
| ~~Email or Telegram test message~~ | removed | D-014 |
| `fallmon freeze` writes frozen config + hash | pass | `results/frozen_config.yaml`, `results/frozen_config.sha256`; hash `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956` |

## Tests
- `pytest`: **71 passed**.
- `test_dashboard.py` (4): test and unknown-ADL trials hidden until unlock; runs, events and feature/rule table from a logged database; log filters by run/mode/subject and table whitelist; full app side-by-side replay (AppTest).
- `test_guards.py` (+3): freeze then check passes and refuses overwrite; check fails without a freeze, after a config change, or after a model file changes; check fails if the frozen file was edited.

## Frozen state (for the thesis)
| Item | Value |
|---|---|
| Frozen at | 2026-10-17 06:45:59 UTC |
| Frozen hash | `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956` |
| DTE | grouped + static labels (D-009), X-003 models |
| OOD threshold | 0.9 (primary); 0.4901 calibrated, reporting only (D-011) |
| Verifier | impact ≥ 3.0 g; at least 2 of {orientation ≥ 30°, post std ≤ 0.12 g, low activity ≥ 1.0 s}; post window 1.5 s; re-arm on |
| Split | `data/splits.json` (test: SA11, SA18, SA19, SA23, SE06, SE11, SE14) |

## Decisions and deviations
- D-014 Console-only notifications.
- Dashboard hides unknown ADLs and test subjects until the final evaluation (stricter than the PRD, which does not say).
- `FALLMON_CONFIG` environment variable lets the dashboard use another config file (used by the tests so they do not write to `logs/fallmon.db`).

## Thesis pointers
- Chapter 4.8 (dashboard): take screenshots of each page yourself (`streamlit run app/dashboard.py`), e.g. a validation fall trial in side-by-side mode, and save them under `results/figures/screenshots/`.
- Chapter 4.9 (testing): freeze/test-lock mechanism, 71 tests.
