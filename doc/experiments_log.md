# Experiments log

Every training, tuning and evaluation run that produced numbers. Newest at the bottom. Copy numbers exactly from the source file.

Entry format:

```
## X-NNN: <run name>
- Date / phase:
- Command:
- Split(s) used:
- Config / hash: (git commit, frozen hash for test runs)
- Machine: (CPU, RAM, OS; once is enough unless it changes)
- Key results: (small table, exact values)
- Source files:
- Notes: (anything surprising; link to limitations.md if relevant)
```

---


## X-001: Data preparation
- Date / phase: 2026-10-16 / Phase 1
- Command: `fallmon prepare-data`
- Split(s) used: index of all subjects (file counts only); conversion check and example plot use train subjects only.
- Config / hash: base commit 327a268 (Phase 1 uncommitted), seed 42
- Machine: Linux 6.8.0-138-generic, Python 3.10.12, CPU only
- Key results: 4,505 trial files, 38 subjects; split train 24 / val 7 / test 7 subjects; standing Am over 120 train D07 trials mean 1.009 g (min 0.967, max 1.097); run time ~10 s.
- Source files: `data/processed/index.parquet`, `data/splits.json`, `results/tables/dataset_summary.*`, `results/tables/splits_summary.*`, `results/figures/phase1_examples.png`
- Notes: 5 SA15 files carry the SE15 name; folder used (D-005).

## X-002: DTE training, as specified in PRD 8
- Date / phase: 2026-10-16 / Phase 2
- Command: `fallmon train`
- Split(s) used: train (known ADLs) for fitting; val known ADLs for early stopping; val falls for the OOD sanity check.
- Config / hash: base commit 782f8a5 + uncommitted Phase 2 code, seed 42, stride 0.24 s (D-008)
- Key results: val macro F1 1.0 s 0.5485, 2.0 s 0.6423, 3.0 s 0.7031, ensemble 0.6940 (accuracy 0.7183). At threshold 0.9: 99.2% of val known-ADL trials and 100% of val fall trials have ≥1 OOD step; step AUROC known vs fall 0.559; trial-min-confidence AUROC 0.380. Training 1,500 s.
- Source files: `models/dte_meta.json`, `models/dte_history.json`, `results/tables/phase2_dte_val.*`, `results/tables/phase2_ood_val.*`, `results/figures/phase2_training_curves.png`, `results/figures/phase2_val_confidence_hist.png`
- Notes: OOD separation is weak; diagnosis in `phase_reports/phase2_baseline_dte.md`. Keep these numbers even if the baseline design changes: they are the as-specified result.

## X-003: DTE training, grouped + static labels (D-009), the variant carried forward
- Date / phase: 2026-10-17 / Phase 2
- Command: `fallmon train` with `dte.label_scheme: grouped_static`
- Split(s) used: as X-002.
- Config / hash: base commit 782f8a5 + uncommitted Phase 2 code, seed 42
- Training label shares (train windows): static 35.0% (1 s), 25.3% (2 s), 16.2% (3 s).
- Key results (validation, development evidence):

| | X-002 as specified | X-003 grouped + static |
|---|---|---|
| Val macro F1, CNN 1 / 2 / 3 s | 0.5485 / 0.6423 / 0.7031 | 0.8025 / 0.8457 / 0.8786 |
| Ensemble step macro F1 (accuracy) | 0.6940 (0.7183) | 0.8191 (0.8432) |
| Median confidence known / falls | 0.827 / 0.700 | 0.986 / 0.913 |
| Known-ADL steps OOD at 0.9 | 57.6% | 36.5% |
| Fall steps OOD at 0.9 | 72.0% | 47.3% |
| AUROC known vs fall, per step | 0.559 | 0.656 |
| AUROC, trial minimum confidence | 0.380 | 0.620 |
| Known-ADL trials with ≥1 OOD step at 0.9 | 99.2% | 97.1% |
| Fall trials with ≥1 OOD step at 0.9 | 100% | 100% |
| Threshold at 95% TPR on val known (note only) | 0.265 | 0.490 |

- Extra validation analyses (ad hoc, no model or parameter chosen from them):
  - Fall trials: the OOD step nearest the impact (argmax Am) is a median 0.16 s away; 99.7% of fall trials have an OOD step within 1.5 s of impact, so events will open where the verifier expects them.
  - Requiring k consecutive OOD steps before alerting, at 0.9: known-ADL trials alerted 97.1% (k=1), 96.3% (k=2), 94.8% (k=3), 89.5% (k=4), 52.2% (k=6); fall trials 100%, 100%, 100%, 98.7%, 77.7%. Not adopted: it does not help without losing falls.
  - At the calibrated threshold 0.490 (k=1): known-ADL trials alerted 66.9%, fall trials 83.3%.
  - Remaining low-confidence known steps cluster in sit/stand/bend/jump trials (D07 median confidence 0.678, D15 0.656), at moving-to-still transitions where the 1 s model sees "static" and the 3 s model still sees movement.
- Source files: `models/dte_meta.json`, `models/dte_history.json`, `results/tables/phase2_dte_val.*`, `results/tables/phase2_ood_val.*`, `results/figures/phase2_training_curves.png`, `results/figures/phase2_val_confidence_hist.png`. X-002 outputs in the `as_specified/` subfolders.

## X-004: Baseline batch replay on validation (stream pipeline)
- Date / phase: 2026-10-17 / Phase 3
- Command: `fallmon batch --split val --mode baseline`
- Split(s) used: val, known ADLs and falls (unknown ADLs excluded)
- Config / hash: base commit d42a0d7 + uncommitted Phase 3 code; models from X-003; run `20261017T055454-baseline-765f17`
- Key results: alerted trials known ADL 370/381 (0.9711), fall 300/300 (1.0000); 496 / 320 alerts. Step OOD rate known 0.3649, fall 0.4729 (identical to X-003 offline). Latency mean 1.746 ms, p95 2.589 ms, max 61.3 ms over 21,748 steps. Wall time 3 min 49 s.
- Fall alert timing (ad hoc): first alert minus impact (argmax Am) median −1.23 s (p5 −4.59, p95 +0.96); 44.0% of fall trials first alerted > 1.5 s before impact; 20 trials with 2 alerts.
- Source files: `results/tables/phase3_batch_val_baseline.*`, `logs/fallmon.db` (run id above)

## X-005: Verifier grid search on validation
- Date / phase: 2026-10-17 / Phase 4
- Command: `fallmon tune-verifier`
- Split(s) used: val known ADLs (381 trials) and falls (300 trials); 7 subjects; unknown ADLs and test excluded (guard 4)
- Config / hash: base commit 1cf9ebf + uncommitted Phase 4 code; DTE from X-003; threshold 0.9
- Grid: 2,430 configurations (PRD grid × rearm_after_reject). Run time 128 s on 8 processes.
- Selected: T_impact 3.0 g, T_orient 30°, T_still 0.12 g, T_rest 1.0 s, impact_and_k_of_3 (k=2), post window 1.5 s, re-arm on. 357 configurations feasible.
- Key results: proposed false-alert rate 0.0079 (3/381), recall 0.9600 (288/300); baseline 0.9711 / 1.0000. First alert minus impact on falls: proposed median +1.84 s (p95 +2.85), baseline −1.23 s (p95 +0.96). 2,458 verifications, 139 truncated.
- Without re-arm: best feasible none; best recall 0.65.
- Source files: `models/verifier_config.json`, `results/tables/verifier_grid_val.csv`, `verifier_grid_val_top.*`, `verifier_selected_config.*`, `results/figures/phase4_val_verifier_features.png`
- Notes: selection-optimistic (chosen on the same trials). T_still optimum at grid edge.

## X-006: Causal vs zero-phase filter check
- Date / phase: 2026-10-17 / Phase 4
- Command: `fallmon filter-check`
- Split(s) used: val known ADLs and falls
- Key results: causal group delay 20.1 ms (1 Hz), 20.8 ms (5 Hz), 23.3 ms (10 Hz). Step OOD rate known 0.3649 vs 0.3640, falls 0.4729 vs 0.4730; AUROC 0.6556 vs 0.6565; mean |Δconfidence| 0.0090. Fall peak Am median 6.49 g vs 6.25 g; peak time shift median 20 ms, max 400 ms.
- Source files: `results/tables/phase4_filter_check.*`
- Notes: models not retrained with zero-phase filtering.

## X-007: Proposed batch replay on validation (stream pipeline)
- Date / phase: 2026-10-17 / Phase 4
- Command: `fallmon batch --split val --mode proposed` (verifier from X-005)
- Run: `20261017T061506-proposed-93e433`
- Key results: alerted trials known ADL 3/381 (0.0079), fall 288/300 (0.9600), exactly matching the tuning replay (X-005). Latency per decision step mean 1.884 ms, p95 2.937 ms, max 53.0 ms over 21,748 steps (baseline X-004: 1.746 / 2.589 ms).
- Source files: `results/tables/phase3_batch_val_proposed.*`, `logs/fallmon.db`

## X-008: Freeze before test evaluation
- Date / phase: 2026-10-17 / Phase 5
- Command: `fallmon freeze`
- Frozen hash: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956` (frozen 2026-10-17 06:45:59 UTC)
- Locks: config, verifier params (X-005), `models/dte_w{1.0,2.0,3.0}s.pt`, `dte_meta.json`, `scaler.json`, `verifier_config.json`, `data/splits.json`
- Source files: `results/frozen_config.yaml`, `results/frozen_config.sha256`
