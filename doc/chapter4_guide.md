# Chapter 4 guide: implementation, testing and results

A suggested outline, with pointers to the notes and generated artefacts for each section. Agents update the **Artefact map** whenever a thesis figure or table is generated.

## Suggested outline

**4.1 Introduction**: restate the aim and the research question (PRD 1.3). Say the system runs on SisFall replay as a simulated IoT stream.

**4.2 Development environment and tools**: stack and reasons (PRD 3). Hardware used for training/evaluation (record CPU, RAM, OS in `experiments_log.md`).

**4.3 System architecture**: pipeline diagram: stream simulator -> preprocessing -> DTE -> OOD -> event logic -> (proposed) verifier -> storage / notifier / dashboard. Baseline vs proposed modes share everything except the verifier.

**4.4 Dataset and preparation**
- SisFall description, verified facts: `dataset_notes.md`
- Activity grouping (known / unknown ADLs / falls) and why: PRD 5.3, `decisions_log.md`
- Preprocessing (filter, downsample, magnitudes, normalisation), causal vs zero-phase: `phase_reports/phase1_*`, `phase4_*`
- Participant-level split: `results/tables/splits_summary.md`

**4.5 Baseline implementation (DTE, Roy et al. 2023)**: model, training, confidence, threshold 0.9. Differences from the paper: `decisions_log.md`.

**4.6 Proposed post-event temporal verification**: impact localisation, features, rules, combination modes, tuning on validation and the selected config: `results/tables/verifier_selected_config.md`, `phase_reports/phase4_*`.

**4.7 Event logic, real-time stream and storage**: merge/cooldown, HOLD state, SQLite schema, notifier with `[SIMULATED]` prefix.

**4.8 Monitoring dashboard**: screenshots of each page (store them in `results/figures/screenshots/`).

**4.9 Testing**: unit tests, leakage guards, test lock / frozen hash. Count of tests and pass result from the latest phase report.

**4.10 Experimental results (test split, frozen config)**: E1 to E7, one subsection each, using the artefact map below. Quote the frozen hash.

**4.11 Demonstration scenarios**: the four cases in `results/demo_cases.json` with their demo figures.

**4.12 Summary of findings**: headline numbers from `results/SUMMARY.md`.

## Artefact map

Fill in as files are generated. "Split" must be stated for every row.

| Thesis section | Artefact | Split | Generated in phase | Notes |
|---|---|---|---|---|
| 4.4 | `results/tables/dataset_summary.md` | all (counts only) | 1 | 4,505 trials, 38 subjects |
| 4.4 | `results/tables/splits_summary.md` | all (counts only) | 1 | seed 42, SE06 forced to test |
| 4.4 | `results/figures/phase1_examples.png` | train (SA01) | 1 | fall F01 vs known D07 vs unknown D10 |
| 4.5 | `results/figures/phase2_training_curves.png` | train/val | 2 | development evidence |
| 4.5 | `results/tables/phase2_dte_val.md`, `phase2_ood_val.md`, `results/figures/phase2_val_confidence_hist.png` | val | 2 | grouped + static (X-003); development evidence |
| 4.5 | same files under `results/*/as_specified/` | val | 2 | as-specified labels (X-002), for the D-009 justification |
| 4.10 E1 | `results/tables/e1_classification.md`, `results/figures/e1_confusion_matrix.png` | test | 6 | |
| 4.10 E2 | `results/tables/e2_ood.md`, `results/figures/e2_confidence_hist_by_group.png`, `e2_roc.png` | test | 6 | |
| 4.10 E3 | `results/tables/e3_verifier.md`, `e3_verifier_features_by_group.png`, `e3_confusion.png` | test | 6 | |
| 4.10 E4 | `results/tables/e4_end_to_end.md`, `e4_baseline_vs_proposed.png` | test | 6 | headline result |
| 4.10 E5 | `results/tables/e5_sweep.md`, `e5_post_window_tradeoff.png` | test (reporting only) | 6 | not used for model selection |
| 4.10 E6 | `results/tables/e6_subgroups.md`, `e6_unknown_adl_breakdown.png` | test | 6 | |
| 4.10 E7 | `results/tables/e7_latency.md`, `e7_latency.png` | test | 6 | |
| 4.11 | `demo_case_fall.png`, `demo_case_unknown_adl.png`, `demo_case_known_adl.png` | test | 6 | |
