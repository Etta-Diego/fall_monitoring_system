# Phase 2 report: Baseline Deep Time Ensemble

- Date completed: 2026-10-17 (as-specified run 2026-10-16, relabelled run 2026-10-17)
- Git commit: (uncommitted at time of writing; base commit 782f8a5)
- PRD sections: 8, 11 (guards 2 and 3), 14 (Phase 2)

## What was built
- `src/fallmon/windowing.py`: loads and preprocesses the trials of a partition; cuts sliding training windows; computes decision-step positions.
- `src/fallmon/dte.py`: the CNN (PRD 8.2) and the `DeepTimeEnsemble` wrapper (mean softmax over the three models; save/load).
- `src/fallmon/ood.py`: confidence = max softmax, `is_ood = confidence < threshold`, `ood_score = 1 - confidence`, threshold at 95% TPR (reporting only).
- `src/fallmon/train.py`: scaler fitting, training loop with early stopping, ensemble validation, figures and tables.
- `src/fallmon/guards.py`: guard 2 (training windows are train-split known ADLs only) and guard 3 (scaler fitted on train subjects only).
- `src/fallmon/utils.py`: seeding (Python, numpy, torch, deterministic ops) and git hash for provenance.
- CLI: `fallmon train`.
- Config: validator rejecting window/stride durations that are not whole samples; `train_stride_s` 0.24 s (D-008).

## How it works (for the thesis)
- **Baseline reproduced:** Roy et al. (2023)'s idea is that a classifier trained only on normal activities is *unsure* when it sees something it has never seen, such as a fall. No official code exists (D-007), so the DTE is reimplemented from the paper's description as specified in PRD 8.
- **Training data:** windows from **known-ADL trials of train-split subjects only** (15 classes, D01–D09, D12, D14–D17, D19). Falls and the four unknown ADLs are never seen in training (guard 2 checks every window).
- **Normalisation:** per-channel z-score (mean, std) fitted on all samples of the train-split known-ADL trials, i.e. the data the windows are cut from; saved to `models/scaler.json` with the list of subjects it was fitted on (guard 3).
- **Windows:** lengths 1, 2 and 3 s (50, 100, 150 samples at 50 Hz), stride 0.24 s (12 samples). Long trials (D01–D04, 100–180 s) would dominate, so each trial gives at most 200 windows, thinned evenly across the trial (`dte.max_windows_per_trial`). Temporal order inside a window is kept.
- **Model (one per window length):** Conv1d(8→32, k5) → BN → ReLU → Conv1d(32→64, k5) → BN → ReLU → MaxPool(2) → Conv1d(64→64, k3) → BN → ReLU → global average pooling → Dropout(0.3) → Linear(64→15). Input channels: ax, ay, az, gx, gy, gz, Am, Gm.
- **Training:** Adam (lr 1e-3, weight decay 1e-4), batch 128, cross-entropy, up to 40 epochs. After each epoch the model is scored on validation known-ADL windows (macro F1); training stops after 6 epochs without improvement and the best epoch's weights are kept. Each model has its own seed (42, 43, 44).
- **Ensemble inference (as at run time):** every 0.5 s, each model gets the latest window of its own length ending at that moment; the three softmax outputs are averaged; confidence = largest averaged probability, predicted activity = its class. The first decision is made once 3 s of data exist.
- **OOD decision:** confidence < 0.9 → out-of-distribution (D-002). The baseline alarms on this directly (Phase 3).

## Acceptance checks
| Check (PRD 14, Phase 2) | Result | Evidence |
|---|---|---|
| 3 models trained; val macro F1 per model and ensemble | pass | `results/tables/phase2_dte_val.md`, `models/dte_meta.json` |
| Guard 2 and 3 pass | pass | run completed with both guards active; unit tests in `test_windowing.py` |
| Val confidence histogram, known ADLs vs falls; falls skew lower | pass | `results/figures/phase2_val_confidence_hist.png`. X-002: median 0.827 known vs 0.700 falls (weak). X-003 (carried forward): 0.986 vs 0.913, step AUROC 0.656 |

The first (as-specified) run passed the checks but its OOD behaviour was too weak for a fair comparison; see "Problem found" and "Resolution" below.

## Tests
- `pytest`: **34 passed** (after D-009: +4 labelling tests in `test_windowing.py`).
- `test_windowing.py` (6): window cap/bounds, temporal order and stride kept, decision steps start at 3 s every 0.5 s, guard 2 rejects fall/unknown codes and non-train subjects, guard 3.
- `test_dte.py` (3): CNN output shape for 1/2/3 s windows, ensemble = mean of per-model softmax and save/load round trip, OOD rule and 95%-TPR threshold.
- `test_config.py` (+1): durations that are not whole samples are rejected.

## Results produced
All numbers: **validation split, development evidence, not final results.** This section is the as-specified run X-002 (training 1,500 s on CPU); the carried-forward run X-003 is under "Resolution".

| Model | Train windows | Val windows | Epochs run | Best epoch | Val macro F1 |
|---|---|---|---|---|---|
| CNN 1.0 s | 91,998 | 26,464 | 21 | 15 | 0.5485 |
| CNN 2.0 s | 86,813 | 24,964 | 24 | 18 | 0.6423 |
| CNN 3.0 s | 81,916 | 23,547 | 20 | 14 | 0.7031 |
| Ensemble (decision steps) | | 14,249 steps | | | 0.6940 (accuracy 0.7183) |

OOD sanity check at threshold 0.9 (`results/tables/phase2_ood_val.md`):

| Metric | Value |
|---|---|
| Known-ADL steps flagged OOD | 57.6% |
| Fall steps flagged OOD | 72.0% |
| Known-ADL trials with ≥1 OOD step | **99.2%** |
| Fall trials with ≥1 OOD step | 100% |
| AUROC known vs fall, per step | 0.559 |
| AUROC known vs fall, trial minimum confidence | **0.380** (below chance) |
| Threshold giving 95% TPR on val known ADLs (note only) | 0.265 |
| Median confidence: known / falls | 0.827 / 0.700 |

Figures: `results/figures/phase2_training_curves.png`, `results/figures/phase2_val_confidence_hist.png`.

## Problem found: max-softmax confidence does not separate falls from known ADLs here
Diagnosis on the validation split (script run ad hoc; numbers below):

1. **Shared still postures carry different labels.** Every window takes its trial's activity code, but most of a 12 s sit/stand trial is the person standing or sitting still, which looks the same in D07, D08, D09, D15, D16, D17. The classifier cannot be sure which code a still window belongs to. Known-ADL steps where the person is still (std of Am over the last 1 s < 0.02 g; 28% of known steps): median confidence **0.452**, 85% flagged OOD. Moving steps: median 0.922, 47% OOD. Per activity, median confidence is lowest for D07 (0.451, 99.8% of steps OOD), D08, D09, D19, D06.
2. **Lying still after a fall looks familiar.** 63% of fall steps are still (post-fall lying), with median confidence 0.741; 40% of all fall steps are predicted as D14 (lying, change of side). So the lowest confidence in a trial is more often in a known ADL than in a fall, hence the trial-level AUROC below 0.5.
3. **Overconfidence on training subjects.** Validation loss rises from epoch 2 while validation macro F1 still creeps up; early stopping on F1 does not control calibration. Secondary to 1 and 2.
4. Main confusions: D03↔D04 (jogging slow/fast, 41%), D05/D06→D17, D09→D07 (half vs low chair, 27%), D15↔D16.

Consequence: with the threshold fixed at 0.9 (D-002), the baseline would alert on almost every known-ADL trial, and the comparison with the proposed system would be against a strawman.

## Resolution: relabelled training (D-009), run X-003
The developer chose option A: merge near-identical activity codes into 8 coarse groups and label still windows (std Am < 0.02 g and mean Gm < 10 °/s over the window) as a shared `static` class. Everything else is unchanged, including threshold 0.9. Full comparison in `experiments_log.md` X-003. Headline (validation):

| | As specified (X-002) | Grouped + static (X-003) |
|---|---|---|
| Ensemble macro F1 on known activities | 0.694 | 0.819 |
| AUROC known vs fall, per step / trial minimum | 0.559 / 0.380 | 0.656 / 0.620 |
| Known-ADL trials with ≥1 OOD step at 0.9 | 99.2% | 97.1% |
| Fall trials with ≥1 OOD step at 0.9 | 100% | 100% |

**What improved:** recognition of known activities, overall confidence on known activities, and fall vs known separation (now better than chance at trial level).

**What did not:** almost every short sit/stand/lie/bend trial still contains at least one step below 0.9, at the moving-to-still transition. Requiring 2–4 consecutive OOD steps does not fix this without losing falls, and even the validation-calibrated threshold (0.49) alerts on 67% of known-ADL trials while missing 17% of falls. **Conclusion: confidence alone is a weak trial-level fall detector on SisFall, under either labelling.** The baseline will therefore have a high false-alert rate; this is a genuine property of the Roy-style approach on this data, not a bug, and it is exactly the gap the verifier targets. Fall events do open at the right place: 99.7% of val fall trials have an OOD step within 1.5 s of impact.

The X-003 models (`models/`) are carried forward. The X-002 models and outputs are archived in `models/as_specified/`, `results/tables/as_specified/`, `results/figures/as_specified/`.

## Decisions and deviations
- D-009 Grouped + static training labels.
- D-007 Reimplementation (no official code).
- D-008 Training stride 0.24 s.
- Scaler fitted on all samples of the train-split known-ADL trials rather than on the stacked (overlapping) windows. Same data, without double-counting the overlap; PRD 6 step 5 intent (train known ADLs only) is unchanged.

## Thesis pointers
- Chapter 4.5 (baseline implementation): this report, `models/dte_meta.json`, `phase2_training_curves.png`.
- Chapter 5.2: the shared-posture finding supports the thesis's gap argument (low confidence is not specific to falls). See `chapter5_guide.md`.

## Open questions for the developer
- Whether Phase 6 should also report the baseline at the validation-calibrated threshold (0.490) as a secondary, reporting-only comparison, alongside the primary 0.9.
