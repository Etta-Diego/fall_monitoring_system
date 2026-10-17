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
