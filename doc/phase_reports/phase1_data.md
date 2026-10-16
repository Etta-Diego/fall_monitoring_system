# Phase 1 report: Data foundation

- Date completed: 2026-10-16
- Git commit: (uncommitted at time of writing; base commit 327a268)
- PRD sections: 5, 6, 7, 11 (guard 1), 14 (Phase 1)

## What was built
- `config/default.yaml` + `src/fallmon/config.py`: every tunable value, validated by pydantic (unknown keys rejected, activity groups must not overlap, `fs_raw` must be a multiple of `target_fs`).
- `src/fallmon/data_loader.py`: parses SisFall files, converts to g and deg/s, builds the trial index (`data/processed/index.parquet`).
- `src/fallmon/preprocessing.py`: Butterworth low-pass, decimation 200 -> 50 Hz, `Am`/`Gm` magnitudes, a sample-by-sample `StreamingPreprocessor`, and the z-score `Scaler` (fitted in Phase 2).
- `src/fallmon/splits.py`: seeded participant-level split with forced-test subjects; refuses to overwrite `data/splits.json` without `--force`.
- `src/fallmon/guards.py`: guard 1 (`assert_no_subject_overlap`).
- `src/fallmon/reporting.py`, `src/fallmon/phase1_report.py`: table/figure writers, conversion check, example plot.
- CLI: `fallmon prepare-data [--force]`, `fallmon show-config`.

## How it works (for the thesis)
- **Parsing.** Each file holds 9 integer columns at 200 Hz. Only the ADXL345 accelerometer (columns 1–3) and ITG3200 gyroscope (4–6) are used; the MMA8451Q (7–9) is ignored (PRD 5.1). The parser tolerates the real-file quirks (missing `;`, trailing blank lines) and rejects any line that does not have 9 values.
- **Unit conversion** (SisFall readme): value = [(2 × Range) / 2^Resolution] × raw. ADXL345: ±16 g, 13 bits -> 0.00390625 g per count. ITG3200: ±2000 °/s, 16 bits -> 0.0610 °/s per count. Config keys `dataset.sensors.*`.
- **Subject identity** comes from the folder, not the file name (D-005), because of the SA15/SE15 mislabelling.
- **Preprocessing** (identical offline and in the stream): 4th-order Butterworth low-pass at 20 Hz (`preprocessing.filter_order`, `lowpass_hz`), causal (`sosfilt`) with the filter state initialised from the first sample so there is no start-up transient; then keep every 4th sample (50 Hz); then append `Am = √(ax²+ay²+az²)` [g] and `Gm = √(gx²+gy²+gz²)` [°/s]. A unit test proves that sample-by-sample streaming output equals the offline output to 1e-10.
- **Split.** Per age group, forced-test subjects (SE06) go to test first; the remaining subjects are shuffled with seed 42 and dealt into test, val, train. Sizes: young 15/4/4, elderly 9/3/3.

## Acceptance checks
| Check (PRD 14, Phase 1) | Result | Evidence |
|---|---|---|
| Index built; dataset summary printed and saved | pass | 4,505 files, 38 subjects; `results/tables/dataset_summary.md` |
| Conversion verified against readme; standing `Am` ≈ 1 g | pass | Readme constants match config. First 1 s of D07 over 120 train-split trials: mean 1.009 g (min 0.967, max 1.097) |
| `splits.json` written; `test_splits.py` passes (no overlap, SE06 rule) | pass | `data/splits.json`; SE06 in test |
| Plots of 1 fall, 1 known ADL, 1 unknown ADL | pass | `results/figures/phase1_examples.png` (train subject SA01) |

## Tests
- `pytest`: **20 passed**.
- `test_config.py` (3): default config loads; overlapping activity groups and unknown keys are rejected.
- `test_data_loader.py` (5): quirk-tolerant parsing, wrong column count rejected, conversion constants, folder-over-filename subject rule, index groups/durations.
- `test_preprocessing.py` (5): streaming == offline causal, 200 -> 50 Hz length, no start-up transient, magnitudes, scaler save/load.
- `test_splits.py` (5): partition sizes, no overlap, SE06 forced to test, determinism, wrong subject count rejected, overwrite refused, committed `splits.json` valid.
- `test_guards.py` (2): overlap detected / disjoint passes.

## Results produced
Dataset summary (all subjects, counts only; `results/tables/dataset_summary.csv`):

| activity_group | age_group | subjects | trials | hours |
|---|---|---|---|---|
| fall | elderly | 1 | 75 | 0.31 |
| fall | young | 23 | 1723 | 7.18 |
| known_adl | elderly | 15 | 738 | 4.49 |
| known_adl | young | 23 | 1354 | 8.00 |
| unknown_adl | elderly | 15 | 155 | 0.51 |
| unknown_adl | young | 23 | 460 | 1.53 |

Split (`data/splits.json`, `results/tables/splits_summary.csv`):

| partition | age_group | subjects | fall | known_adl | unknown_adl |
|---|---|---|---|---|---|
| train | elderly | 9 | 0 | 435 | 85 |
| train | young | 15 | 1123 | 883 | 300 |
| val | elderly | 3 | 0 | 146 | 30 |
| val | young | 4 | 300 | 235 | 80 |
| test | elderly | 3 | 75 | 157 | 40 |
| test | young | 4 | 300 | 236 | 80 |

- Train: SA01–06, SA09, SA10, SA12–15, SA20–22, SE01–04, SE08–10, SE12, SE13.
- Val: SA07, SA08, SA16, SA17, SE05, SE07, SE15.
- Test: SA11, SA18, SA19, SA23, SE06, SE11, SE14.
- Train falls and train/val unknown ADLs appear in the table because they exist on disk; per PRD 7.2 they are **not used** for training or tuning (enforced by guard 2 in Phase 2 and guard 4 in Phase 4).
- Test-split trial contents were not opened; only file counts were used.

## Decisions and deviations
- D-004 Python 3.10 instead of 3.11.
- D-005 Subject ID from folder (SA15/SE15 quirk).
- D-006 Dataset obtained from GitHub mirror; 4,505 files vs 4,510 in readme.
- Config additions not in PRD Section 17: `dataset.processed_dir`, `dataset.splits_path` (paths only, no behavioural change).

## Problems and limitations found
See `limitations.md` "Found during the build": thin elderly unknown-ADL coverage (D10/D11 only), elderly falls from one person (SE06), 5 missing trials.

## Thesis pointers
- Chapter 4.4 (dataset and preparation): this report, `dataset_notes.md`, `dataset_summary.md`, `splits_summary.md`, `phase1_examples.png`.
- The example figure is a good motivating illustration for Chapter 4.6 / 5.2: see `chapter5_guide.md`.

## Open questions for the developer
- None blocking. Confirm you're happy with the split before Phase 2 trains on it (changing it later means retraining).
