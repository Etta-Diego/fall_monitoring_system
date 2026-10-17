# Phase 4 report: Post-event temporal verifier

- Date completed: 2026-10-17
- Git commit: (uncommitted at time of writing; base commit 1cf9ebf)
- PRD sections: 6.1, 9, 10, 11 (guard 4), 14 (Phase 4)

## What was built
- `src/fallmon/verifier.py`: impact localisation, the six features, the four rules, three combination modes, human-readable reasons, `VerifierParams` (save/load).
- `src/fallmon/pipeline.py` (refactored): `DecisionEngine` holds all event/alert/hold/verify logic with no I/O and no model; `StreamProcessor` = preprocessing + DTE + engine + logging. Proposed mode added.
- `src/fallmon/tune_verifier.py`: validation-only grid search (computes DTE confidences once, replays the engine for each configuration on 8 processes).
- `src/fallmon/filter_check.py`: causal vs zero-phase check (PRD 6.1).
- `src/fallmon/events.py`: `blocked` (no new event while a verification is pending) and `end_current` (re-arm).
- `src/fallmon/guards.py`: guard 4.
- CLI: `fallmon tune-verifier`, `fallmon filter-check`; `stream` and `batch` now accept `--mode proposed|both`.

## How it works (for the thesis)
When the DTE's confidence drops below 0.9 and an event opens, the proposed system does **not** alert. It holds the event and:
1. **Finds the impact:** the largest acceleration magnitude Am within 1.5 s before to 1.0 s after the event opened.
2. **Waits** until `post_window_s` seconds after the impact have streamed in (or the trial ends: `truncated`).
3. **Measures, in physical units** (unnormalised, filtered signals):
   - `impact_peak_g`: largest Am within ±0.5 s of the impact;
   - `gyro_peak_dps`: largest Gm within ±0.5 s (reported, not used by a rule);
   - `orientation_change_deg`: angle between the average gravity direction 2–1 s before the impact and from 1 s after the impact to the end of the post window;
   - `post_am_std_g`: variation of Am in that post interval (low = lying still);
   - `post_gm_mean_dps`: average rotation in the post interval (reported);
   - `low_activity_s`: longest stretch in the post interval where the 0.5 s rolling std of Am is below 0.05 g.
4. **Applies rules:** R_impact (impact ≥ T_impact), R_orient (orientation ≥ T_orient), R_still (post std ≤ T_still), R_rest (low activity ≥ T_rest), combined as `impact_and_any`, `impact_and_k_of_3` or `all`.
5. **Decides:** VERIFIED -> alert (and alert log, 10 s cooldown); REJECTED -> no alert, entry in the unknown-activity log, and (with re-arm, D-012) the event ends so a later impact can be checked on its own.

Every event row stores the features, each rule's pass/fail, and a reason such as `impact 3.21 g >= 3 g; orientation change 74.10 deg >= 30 deg; post std 0.05 g <= 0.12 g; low activity 0.52 s < 1 s [impact_and_k_of_3, k=2] -> VERIFIED`.

**Tuning (validation only).** The grid of PRD 17 plus `rearm_after_reject` (2,430 configurations) was evaluated on the 381 known-ADL and 300 fall trials of the 7 validation subjects; unknown ADLs and the test split were never used (guard 4 checks the tuning data). Objective: lowest known-ADL false-alert rate (share of known-ADL trials with at least one alert) with fall recall ≥ 0.95. Ties: shorter post window, simpler combination, no re-arm, higher recall, grid order.

## Acceptance checks
| Check (PRD 14, Phase 4) | Result | Evidence |
|---|---|---|
| Synthetic tests: fall-shaped signal verifies, sit-down-shaped signal rejects | pass | `tests/test_verifier.py`: fall (impact, 90° orientation change, lying still) -> VERIFIED; hard sit-down (3 g impact, 15° tilt, walks away) -> REJECTED although R_impact passes |
| Grid search on validation only (guard 4 passes); selected config saved with val recall and val FPR | pass | `models/verifier_config.json`, `results/tables/verifier_selected_config.md`, `results/tables/verifier_grid_val.csv` |
| Causal vs zero-phase filter check reported | pass | `results/tables/phase4_filter_check.md` |

## Tests
- `pytest`: **64 passed**.
- `test_verifier.py` (7): fall verifies; hard sit-down rejects; weak impact rejects; impact localisation picks the largest peak in the search window; NaN features without post data make rules false; combination modes; parameter save/load.
- `test_pipeline.py` (+5): proposed mode holds then alerts on a fall (decision ≥ 1.5 s after event, `[SIMULATED] Verified fall alert`, event reason ends with VERIFIED); rejects a hard sit-down and writes the unknown-activity log; **re-arm catches a fall hidden inside an early event that the PRD behaviour misses**; truncated verification at trial end; **tuning replay gives the same alerts as the stream processor** (with and without re-arm).
- `test_guards.py` (+1): guard 4 rejects unknown ADLs, test subjects and train subjects.

## Results produced (validation split, development evidence, not final)
Selected configuration (`models/verifier_config.json`): T_impact 3.0 g, T_orient 30°, T_still 0.12 g, T_rest 1.0 s, `impact_and_k_of_3` with k = 2, post window 1.5 s, re-arm on. 357 of 2,430 configurations met the recall constraint.

| Validation (681 trials) | Baseline | Proposed |
|---|---|---|
| Known-ADL trials with an alert (false-alert rate) | 370/381 = 0.9711 | **3/381 = 0.0079** |
| Fall trials with an alert (recall) | 300/300 = 1.0000 | **288/300 = 0.9600** |
| Alerts on known-ADL trials | 496 | 3 |
| First alert minus impact, falls: median / p95 | −1.23 s / +0.96 s | **+1.84 s / +2.85 s** |
| Falls first alerted > 1.5 s before impact | 44.0% | 0.0% |
| Verifications run (truncated) | – | 2,458 (139) |

Rule pass rates over all events reaching the verifier (selected configuration):

| | R_impact | R_orient | R_still | R_rest |
|---|---|---|---|---|
| Fall trial events | 0.588 | 0.788 | 0.765 | 0.000 |
| Known-ADL trial events | 0.053 | 0.265 | 0.857 | 0.000 |

(Fall trials produce several events each with re-arm, including pre-fall ones, so R_impact < 1 for fall-trial events is expected.)

Grid analysis (`verifier_grid_val.csv`):
- **Without re-arm no configuration meets the constraint (best fall recall 0.65); with re-arm the best recall is 1.00.** The PRD's single verification per event misses falls whose event opened early.
- `impact_and_k_of_3` beats `impact_and_any` (best feasible false-alert rate 0.0079 vs 0.0709); `all` never meets the constraint (R_rest is unreachable at short post windows).
- Best feasible false-alert rate by T_impact: 1.8 g 0.026, 2.0 g 0.021, 2.5 g 0.013, **3.0 g 0.008**, 3.5 g 0.071 (interior optimum).
- By T_still: 0.05 g 0.071, 0.08 g 0.018, **0.12 g 0.008**. The optimum is at the **edge of the grid**, so a larger value might do as well or better; the PRD grid was kept as specified.

**Stream consistency (X-007):** `fallmon batch --split val --mode proposed` through the real `StreamProcessor` gives the same 3/381 and 288/300 as the tuning replay. Latency per decision step: mean 1.88 ms, p95 2.94 ms (baseline 1.75 / 2.59 ms), so verification adds about 0.1–0.3 ms.

**Example (`fallmon stream --trial F05_SA01_R01 --mode both`, train subject):** baseline alerts at 7.00 s on low confidence; proposed holds from 7.00 s and alerts at 8.50 s with `impact 6.03 g >= 3 g; orientation change 85.49 deg >= 30 deg; post std 0.02 g <= 0.12 g; low activity 0.42 s < 1 s [impact_and_k_of_3, k=2] -> VERIFIED`.

Filter check (`phase4_filter_check.md`): causal filter delay ≈ 20 ms (one 50 Hz sample) at 1–5 Hz, 23 ms at 10 Hz. Feeding zero-phase input to the causally trained DTE changes step OOD rates by < 0.001 and AUROC from 0.6556 to 0.6565 (mean |Δconfidence| 0.009). Fall impact peaks: median 6.49 g causal vs 6.25 g zero-phase; peak time shift median 20 ms (max 400 ms, one trial where two near-equal peaks swap). **Conclusion: the causal default (D-003) costs nothing measurable; no change.** Models were not retrained with zero-phase filtering.

## Decisions and deviations
- D-012 Re-arm after rejection (selected by the tuning objective).
- D-013 Feature windows configurable; rest-rule reachability note.

## Problems and limitations found
- **Validation numbers are optimistic**: the configuration was chosen on these same trials from 2,430 candidates. Only the Phase 6 test numbers count.
- **R_rest is unreachable** with the selected 1.5 s post window (post interval only 0.5 s long; D-013). The effective rule is impact ≥ 3.0 g and orientation change ≥ 30° and post std ≤ 0.12 g.
- **T_still at the grid edge** (0.12 g).
- **Truncation:** 139 of 2,458 val verifications ran out of trial before the post window ended (falls are 15 s trials).

## Thesis pointers
- Chapter 4.6 (proposed verification): this report, `verifier.py`, `verifier_selected_config.md`, `phase4_val_verifier_features.png`.
- Chapter 4.4 / 4.5: `phase4_filter_check.md` justifies the causal filter.
- Chapter 5.2: re-arm finding (single post-event check per event is not enough when OOD events open before the impact).
