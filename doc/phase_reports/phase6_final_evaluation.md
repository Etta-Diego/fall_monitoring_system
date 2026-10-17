# Phase 6 report: Final evaluation (test split)

- Date completed: 2026-10-17
- Git commit: (evaluation code uncommitted at run time; base commit a28eaf2). Frozen config SHA-256 `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956` (models, verifier, config, split).
- PRD sections: 13, 14 (Phase 6), 15
- Command: `fallmon evaluate --split test --all` (run once, 594 s). A dry run on validation (`--split val`, outputs in `results/dryrun_val/`) was done first to debug the pipeline without touching the test split; it reproduced the Phase 3/4 validation numbers exactly.

## What was built
- `src/fallmon/evaluation.py`: experiments E1–E7, bootstrap CIs, exact McNemar, demo-case selection and plots, `results/SUMMARY.md`.
- `src/fallmon/reporting.py`: frozen hash stamped on every table (Markdown header + CSV `#` comment line) and every figure (footer + PNG metadata).
- CLI: `fallmon evaluate --split test|val --all [--rerun]` (refuses without a valid freeze; refuses a second test run without `--rerun`), `fallmon demo --case N --speed N` (only after the final evaluation).
- `tests/test_evaluation.py`: hand-computed metric checks, false alerts per hour, seeded bootstrap, McNemar pairing.

## How the evaluation works (for the thesis)
- **Test set:** all trials of the 7 test subjects (SA11, SA18, SA19, SA23, SE06, SE11, SE14): 393 known-ADL, **120 unknown-ADL** (never seen by any trained or tuned component) and 375 fall trials.
- **Primary results** come from real stream runs: every trial replayed sample by sample through the `StreamProcessor` in baseline and proposed mode (same trials, same models, threshold 0.9, notifications off), logged in SQLite with the frozen hash.
- **Trial-level outcome:** a trial is alerted if at least one ALERT was emitted. Reference impact of a fall trial = time of max Am over the filtered trial; decision delay = first alert − reference impact.
- **Uncertainty:** 95% percentile bootstrap CIs, 1,000 resamples over trials, seed 42. **Significance:** exact McNemar test on paired per-trial correctness, separately for falls and non-falls.
- **Consistency checks** (all passed): streamed confidences equal offline confidences (max difference 5.96e-07 over 26,516 steps); the decision-engine replay gives identical alert counts per trial to the stream runs for both modes.
- **Secondary results** (calibrated threshold 0.4901, D-011; post-window sweep E5) use the replay. E5 is reporting only.
- **Demo cases** are chosen by fixed rules (first trial by id satisfying each rule), not by eye.

## Acceptance checks
| Check (PRD 14, Phase 6) | Result | Evidence |
|---|---|---|
| All E1–E7 tables and figures from one command | pass | `fallmon evaluate --split test --all`; tables `results/tables/e1_*`…`e7_*`, figures `results/figures/e1_*`…`e7_*`, `demo_case_*.png` |
| Every output file header carries the frozen hash | pass | Markdown "Frozen config SHA-256" line, CSV `# frozen_config_sha256:` first line, figure footer + PNG metadata |
| `results/SUMMARY.md` auto-generated with headline numbers, CIs, McNemar p-values, failure cases | pass | `results/SUMMARY.md` |

Tests: **75 passed**.

## Results (test split, final)

### E4 headline (trial level, 95% bootstrap CI)
| Metric | Baseline | Proposed |
|---|---|---|
| Sensitivity (falls alerted) | 1.000 [1.000, 1.000] | **0.803 [0.760, 0.842]** |
| FPR known ADLs | 0.962 [0.942, 0.980] | **0.003 [0.000, 0.008]** |
| FPR unknown ADLs | 1.000 [1.000, 1.000] | **0.042 [0.009, 0.083]** |
| Precision | 0.430 [0.398, 0.461] | 0.980 [0.963, 0.994] |
| F1 | 0.601 [0.569, 0.631] | 0.883 [0.854, 0.909] |
| Specificity | 0.029 | 0.988 |
| Accuracy | 0.439 | 0.910 |
| False alerts (count) | 618 | 6 |
| False alerts per hour of non-fall recording | 225.8 | 2.19 |
| Decision delay median / p95 [s] | −1.40 / +0.47 | +1.88 / +2.88 |
| Falls first alerted > 1.5 s before impact | 44.5% | 0.0% |
| Processing latency mean / p95 [ms] | 1.66 / 2.21 | 1.84 / 2.82 |

- **False-alert reduction: 99.0%** (618 → 6).
- **McNemar, non-falls:** p = 1.6e-148 (proposed correct where baseline wrong in 492 trials; never the reverse).
- **McNemar, falls:** p = 1.1e-22 (baseline correct where proposed wrong in 74 trials; never the reverse). **The sensitivity loss is statistically significant.**
- Counts: baseline TP 375, FN 0, FP 498, TN 15; proposed TP 301, FN 74, FP 6, TN 507 (see `e4_end_to_end.md`).

### E1 DTE recognition (known ADLs, per step)
Accuracy 0.8739, macro F1 0.8412 (9 classes: 8 activity groups + static). `e1_classification.md`, `e1_confusion_matrix.png`.

### E2 OOD detection by confidence alone
| Comparison | AUROC per step | AUROC per trial (min confidence) |
|---|---|---|
| known vs falls | 0.684 | 0.644 |
| known vs unknown ADLs | 0.634 | **0.420** |
| known vs falls + unknown | 0.674 | 0.590 |
Confidence alone is a weak separator; per trial, unknown ADLs are *not* less confident than known ADLs. `e2_ood.md`, `e2_ood_rates.md`, `e2_*.png`.

### E3 the verifier on its own
| Event type | Events | Verified | R_impact | R_orient | R_still |
|---|---|---|---|---|---|
| Fall impact (within 1 s of reference impact) | 460 | 298 (64.8%) | 0.665 | 0.998 | 0.924 |
| Fall trial, other event | 333 | 3 | 0.012 | 0.387 | 0.478 |
| Known ADLs | 1,783 | 1 | 0.074 | 0.257 | 0.880 |
| Unknown ADLs | 429 | 5 | 0.110 | 0.291 | 0.795 |
R_rest passed for no event (unreachable with the 1.5 s post window, D-013). `e3_verifier.md`, `e3_confusion.png`, `e3_verifier_features_by_group.png`.

### E5 post-window sweep (reporting only)
| Post window [s] | Sensitivity | FPR known | FPR unknown | Median delay [s] |
|---|---|---|---|---|
| 1.0 | 0.000 | 0.000 | 0.000 | – (post interval empty) |
| **1.5 (selected)** | 0.803 | 0.003 | 0.042 | 1.88 |
| 2.0 | 0.803 | 0.087 | 0.125 | 2.38 |
| 3.0 | 0.627 | 0.104 | 0.092 | 3.28 |
| 4.0 | 0.541 | 0.084 | 0.050 | 4.28 |

### E6 subgroups
| Subgroup | System | Sensitivity | FPR known | FPR unknown |
|---|---|---|---|---|
| Young (4 subjects) | baseline | 1.000 | 0.962 | 1.000 |
| Young | proposed | 0.837 | 0.004 | 0.050 |
| Elderly (3 subjects; falls = SE06 only) | baseline | 1.000 | 0.962 | 1.000 |
| Elderly | proposed | 0.667 | 0.000 | 0.025 |

Unknown ADLs by code, proposed (baseline alerted on 100% of every code): D10 0/35, **D11 5/35**, D13 0/25, D18 0/25.

### E7 latency
Mean 1.66 ms (baseline) / 1.84 ms (proposed) per decision step, p95 2.21 / 2.82 ms, on CPU, against a 500 ms decision interval. `e7_latency.md`, `e7_latency.png`.

### Calibrated threshold 0.4901 (secondary, D-011)
Baseline: sensitivity 0.821, FPR known 0.682, FPR unknown 0.567, 135.9 false alerts/h. Proposed: sensitivity 0.515, FPR 0 and 0. A better-calibrated baseline still raises a false alert on most normal trials; the verifier (tuned at 0.9) loses more falls at this threshold because fewer events reach it.

## Analysis of the failures (post-hoc explanation; nothing was changed)
- **Missed falls (74).** In 73 of them the verifier *did* examine the real impact: orientation change passed in 99% and stillness in 92%, but the **impact peak was below 3.0 g** (median 2.17 g; 96% under 3.0 g). The remaining one (F05_SA23_R02) was never verified at the impact.
- **Concentrated by subject:** SA23 35/75 missed, SE06 25/75, SA19 7/75, SA18 4/75, SA11 3/75 (validation subjects: 1–4 of 75 each). SE06 is the judo expert; trained break-falls are softer. The 3.0 g threshold was chosen on validation subjects whose falls happened to be harder, so it **did not generalise to all test subjects**: the validation recall constraint (≥ 0.95) was met on validation (0.960) but not on test (0.803).
- **Concentrated by fall type:** F10 fall forward when sitting down 13/25, F13 fall forward while sitting 11/25, F07 fainting with hands on a table 8/25, F08 forward when getting up 8/25, F14 7/25. These are low-energy falls with shorter drop height.
- **False alerts (6):** D11 "collapse into a chair" 5 (4 trials of SA18, 1 of SE11) and D14 lateral lying 1 (SA11). A collapse into a chair has a real impact and a posture change, which is what the verifier looks for.

## Demo cases (`results/demo_cases.json`)
| Case | Trial | Outcome |
|---|---|---|
| 1 genuine fall | F01_SA11_R01 | both alert; proposed alerts after a verified impact |
| 2 unseen fall-like ADL | D10_SA11_R01 | baseline false alert at 3.0 s; proposed HOLD → REJECTED |
| 3 known ADL | D01_SA19_R01 | no event in either system |
| 4 failure | D11_SA18_R01 | proposed still alerts on a collapse into a chair |
Replay with `fallmon demo --case N --speed 5`; figures `demo_case_{fall,unknown_adl,known_adl,failure}.png`.

## Thesis pointers
- Chapter 4.10–4.12: tables and figures above; SUMMARY.md for the headline; quote the frozen hash.
- Chapter 5: see `chapter5_guide.md` (trade-off, subject effect, impact threshold, D11, confidence alone is weak, delay).
