# Phase 7 report: Documentation

- Date completed: 2026-10-17
- Git commit: (uncommitted at time of writing; base commit 94687cf)
- PRD sections: 14 (Phase 7), 19 (definition of done)

## What was built
- `README.md`, written for the student writing the thesis (and readable by a supervisor or examiner): purpose, honesty statement, a one-picture explanation of baseline vs proposed, headline test results, how to use `doc/` and `results/` for Chapters 4 and 5, setup, dataset placement, every CLI command in order with run times and outputs, the safety rails (test lock, leakage guards), how to reproduce results (exactly, or from scratch), the dashboard, a stage-by-stage explanation for Chapter 4, project structure, decisions that changed the plan, limitations, tests, glossary, references.
- D-015: model weights committed so a clean clone plus the dataset reproduces the frozen results.
- D-016: handover packaging. Everything in git except the raw dataset (index and log database now committed). README restructured so section 4 is the presentation guide (dashboard, what works without raw data, the one-line dataset download, a four-case presentation sequence on test data), placed before Setup. `fallmon stream` accepts test trials after the final evaluation; dashboard and CLI explain how to fetch the raw data when it is missing.

## Acceptance checks
| Check (PRD 14, Phase 7) | Result | Where in README |
|---|---|---|
| Purpose | pass | intro, §1 |
| Honesty statement | pass | "Honesty statement" |
| Setup | pass | §5 |
| Dataset placement | pass | §4.1 and §5 "Raw dataset" (one-line download) |
| Every CLI command in order | pass | §5 |
| How to reproduce results | pass | §7 (exact rerun verified, see below) |
| How to run the dashboard | pass | §4 (presentation guide) |
| Known limitations | pass | §11 |

## Reproducibility check
`fallmon evaluate --split test --all --rerun` was run a second time (579 s) with the committed models and frozen config (hash `9b9867ac…f956`) and compared file by file with the first run:
- **Identical:** every count, rate, confidence interval, McNemar p-value, AUROC, E1/E2/E3/E5/E6 table, per-trial outcome, failure-case list and demo-case choice.
- **Different, as expected:** run ids, and processing latency (wall-clock timing): mean 1.660 → 1.608 ms (baseline) and 1.841 → 1.811 ms (proposed); p95 2.206 → 2.203 and 2.816 → 2.753 ms; max 49.8 → 37.3 and 85.2 → 57.3 ms (rerun values from `results/tables/e7_latency.md` before the first run's files were restored).
- The first run's outputs (X-010) are kept in `results/` because they are the ones quoted in `doc/`; the second run is in `logs/fallmon.db`.

## Definition of done (PRD 19)
| Item | Status |
|---|---|
| All phases accepted | Phases 1–6 accepted by the developer; Phase 7 pending review |
| `pytest` passes | 76 passed |
| `fallmon evaluate --split test --all` regenerates every Chapter 4 table and figure from a clean clone plus the dataset | yes, with the committed models (`--rerun`, since SUMMARY.md exists); see reproducibility check |
| Dashboard demonstrates the four demo scenarios | demo trials available in Live Replay after the final evaluation; `fallmon demo --case 1..4` in the terminal. Not visually checked by the agent. |
| README honesty statement present; no text claims physical deployment or real elderly falls | yes |
