# Fall Monitoring System with Post-Event Temporal Verification

Software artefact for the thesis **"Design and Development of an Enhanced IoT-Based System for Reliable Real-Time Fall Classification and Alert Verification in Elderly Care."**

This repository contains everything behind Chapters 4 and 5: the code, the trained models, the frozen configuration, every result table and figure, and a running record of decisions (`doc/`). This README is written for the person writing the thesis: what the system does, how to run it, where each result comes from, and what you can and cannot claim.

---

## Honesty statement (read first)

- **There is no hardware.** All data is the public **SisFall dataset replayed sample by sample as a simulated IoT stream**. Every screen, log and alert says "SisFall dataset replay (simulated IoT stream)", and every alert starts with `[SIMULATED]`.
- **The falls are simulated falls from SisFall**, performed by young volunteers and one older participant (SE06, a judo expert). They are not real falls of older adults. Do not call them "elderly falls".
- **The baseline is a reimplementation** of Roy et al. (2023) from the paper's description. No official code exists. It also uses modified training labels (decision D-009). Say so in Chapter 4.
- **Results are reported exactly as computed**, including failures. The proposed system misses about one fall in five on the test subjects, and the thesis must say so.

---

## 1. What the system does, in one picture

The thesis takes Roy et al. (2023) as the existing system. Their idea: train a classifier on **normal activities only**. When it is *unsure* (low confidence), the movement is unfamiliar ("out of distribution", OOD) and is treated as a fall. The weakness, identified in Chapter 2: unfamiliar but harmless movements are also unsure, so they raise false alarms.

The contribution of this thesis is a **post-event temporal verification** stage between "unsure" and "alarm":

```
 SisFall trial ──► replayed sample by sample (200 Hz, simulated IoT stream)
                     │
                     ▼
            filter, downsample to 50 Hz, add Am/Gm, normalise
                     │
                     ▼
      Deep Time Ensemble: 3 small CNNs (1 s, 2 s, 3 s windows), every 0.5 s
      confidence = highest averaged probability
                     │
          confidence < 0.9 ?  ──no──► KNOWN activity (activity log)
                     │ yes
                     ▼
               OOD EVENT opens
          ┌──────────┴───────────────────────────────┐
     BASELINE (Roy et al.)                   PROPOSED (this thesis)
     alert immediately                       HOLD: find the impact, wait 1.5 s,
                                             check physical evidence:
                                              • impact ≥ 3.0 g, and at least 2 of
                                              • orientation change ≥ 30°
                                              • lying still (Am std ≤ 0.12 g)
                                              • low-activity run ≥ 1.0 s
                                                  │
                                       VERIFIED ──┴── REJECTED
                                       alert +        no alert, unknown-activity
                                       alert log      log, re-check later impacts
```

Both systems share everything except the verifier: same data, models, threshold and event logic. So any difference in results comes from the verification stage alone.

---

## 2. Headline results (test split, final)

From `results/SUMMARY.md`. 7 held-out subjects (SA11, SA18, SA19, SA23, SE06, SE11, SE14); 393 known-ADL, 120 unknown-ADL and 375 fall trials. A trial counts as "alerted" if at least one alert was raised in it. Brackets are 95% bootstrap confidence intervals.

| Metric | Baseline | Proposed |
|---|---|---|
| Falls detected (sensitivity) | 1.000 [1.000, 1.000] | **0.803** [0.760, 0.842] |
| False-alert rate, known activities | 0.962 [0.942, 0.980] | **0.003** [0.000, 0.008] |
| False-alert rate, unseen fall-like activities | 1.000 [1.000, 1.000] | **0.042** [0.009, 0.083] |
| Precision / F1 | 0.430 / 0.601 | **0.980 / 0.883** |
| False alerts per hour of normal activity | 225.8 | **2.2** |
| Alert time relative to impact (median) | −1.40 s (often before the fall) | +1.88 s |
| Processing time per decision (mean) | 1.66 ms | 1.84 ms |

- **False alerts fell by 99.0%** (618 → 6). McNemar exact test, non-falls: p = 1.6 × 10⁻¹⁴⁸.
- **The cost is sensitivity** (1.000 → 0.803), also significant (falls: p = 1.1 × 10⁻²²). In 73 of the 74 missed falls the verifier saw the posture change and the stillness, but the impact was below 3.0 g (median 2.17 g). The misses come mostly from two subjects, SA23 and SE06 (the judo expert), and from low-energy falls while sitting down.
- Validation numbers (fall recall 0.960, false-alert rate 0.008) were better than test. The difference is the subject effect described above; see `doc/phase_reports/phase6_final_evaluation.md`.

---

## 3. Using this repository to write Chapters 4 and 5

For presenting, see section 4. For writing, start with **`doc/README.md`**. The `doc/` folder was written during the build, phase by phase, for exactly this purpose.

| You are writing… | Read |
|---|---|
| Chapter 4 outline and which figure/table goes where | `doc/chapter4_guide.md` (artefact map) |
| Dataset description, verified facts, quirks | `doc/dataset_notes.md` |
| Why each design choice was made (and deviations from the plan) | `doc/decisions_log.md` (D-001 … D-015) |
| How each part was built and tested | `doc/phase_reports/phase1_data.md` … `phase6_final_evaluation.md` |
| Every number, with the command and source file | `doc/experiments_log.md` (X-001 … X-010) |
| Limitations, threats to validity, failure cases | `doc/limitations.md` |
| Discussion, conclusion, recommendations, future work | `doc/chapter5_guide.md` |
| Final numbers | `results/SUMMARY.md`, `results/tables/e*.md`, `results/figures/e*.png` |

Two rules when quoting numbers:
1. **Only test-split numbers (Phase 6) are results.** Files named `phase2_*`, `phase3_*`, `phase4_*`, `verifier_*` and everything under `results/dryrun_val/` are validation-split *development evidence*. Use them to explain choices, not as performance.
2. **Quote the frozen hash** (`9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`). It is printed at the top of every final table and in the corner of every final figure, and proves the results come from the locked setup.

---

## 4. Presenting the system: the dashboard and live demos

Everything needed for a presentation is already in the repository: trained models, frozen configuration, final results and the log database of the official test runs. Nothing has to be retrained or re-evaluated. Only **live replays** need the raw SisFall data (see 4.1).

### 4.1 What works straight after cloning, and what needs the raw data

| Feature | Without raw data | With raw data |
|---|---|---|
| Dashboard **Results** page (all final tables and figures) | yes | yes |
| Dashboard **Event Details** and **Logs** pages (official test runs, every event with its reason) | yes | yes |
| `results/SUMMARY.md`, `results/tables/`, `results/figures/` | yes | yes |
| Dashboard **Live Replay** (watch a trial stream in, baseline vs proposed) | no | yes |
| `fallmon demo`, `fallmon stream` (live replay in the terminal) | no | yes |
| `fallmon evaluate --rerun` (regenerate the results) | no | yes |

Live replay feeds the original sensor recordings through the models, so those recordings must be present. Download them once, from the project folder (about 1 GB, a few minutes):

```bash
git clone https://github.com/Fall-Prevention-Team/sisfallData.git data/raw/SisFall_dataset && git -C data/raw/SisFall_dataset checkout 8352a0f
```

This puts the exact copy used in this work (commit `8352a0f`, 4,505 trial files) where the code expects it. Without it, the Live Replay page shows this command instead of failing.

### 4.2 Start the dashboard

```bash
source .venv/bin/activate          # after the setup in section 5
streamlit run app/dashboard.py     # opens http://localhost:8501 in the browser
```

A banner on every page says "Data source: SisFall dataset replay (simulated IoT stream). No physical device."

| Page | What it shows |
|---|---|
| **Live Replay** | Pick a subject, a trial, the mode (baseline / proposed / **side by side**) and the speed. For each mode: stream status, predicted activity, a confidence gauge with the 0.9 threshold, OOD flag, verification state (HOLD → VERIFIED or REJECTED), the decision, and the number of alerts. A rolling 10 s chart of Am (acceleration) and Gm (rotation) marks where an event opened (dashed line), the located impact (▼) and the final decision (solid line), in red for baseline and green for proposed. Each replay is logged. |
| **Event Details** | Pick a run and an event: final decision, confidence, decision delay, processing time, the full reason text, and every verifier measurement next to its threshold with PASS/FAIL. The official test runs are the runs labelled `test`. |
| **Logs** | Activity log, unknown-activity log and alert log, filtered by run, mode and subject. |
| **Results** | Every final table and figure, read-only. |

Because the final evaluation is complete, **all test-split trials, including the unseen fall-like activities, can be replayed.** (Before the final evaluation they were locked, so nobody could tune the system by looking at them.)

### 4.3 A suggested presentation sequence (test data)

Use **side by side** mode, speed 5–10×. These are the four demo cases chosen by fixed rules during the final evaluation (`results/demo_cases.json`):

| # | What it shows | Subject → trial in Live Replay | Expected outcome |
|---|---|---|---|
| 1 | A genuine fall is caught by both | SA11 → `F01_SA11_R01` (fall forward after a slip) | Baseline alerts immediately; proposed holds, finds the impact, then raises a verified alert ~2 s later |
| 2 | **The contribution:** an unseen fall-like activity | SA11 → `D10_SA11_R01` (quick sit in a low chair) | Baseline raises a false alert at 3.0 s; proposed holds, then **rejects** it (no hard impact), logged as unknown activity |
| 3 | A normal activity | SA19 → `D01_SA19_R01` (walking slowly) | Neither system opens an event |
| 4 | An honest failure case | SA18 → `D11_SA18_R01` (collapse into a chair) | Proposed still alerts: a collapse has an impact and a posture change |

After each replay, open **Event Details**, select the run just created and the event, and show the measurements against the thresholds: this is where the "why" of each decision is visible. To show the overall picture, finish on the **Results** page with `e4_baseline_vs_proposed.png` and `e6_unknown_adl_breakdown.png`.

The same cases also run in the terminal, which is handy as a backup if the browser misbehaves:

```bash
fallmon demo --case 2 --speed 5                                # 1 fall, 2 unseen ADL, 3 normal, 4 failure
fallmon stream --trial F04_SE06_R01 --mode both --speed 5      # any trial id, e.g. a fall by SE06
```

Trial ids follow `<activity>_<subject>_R<trial>` (e.g. F04 = fall forward while walking caused by a trip, SE06 = older participant 06, trial 1); the full list of activity codes is in the SisFall readme, `data/raw/SisFall_dataset/Readme.txt`.

---

## 5. Setup

Tested on Linux with **Python 3.10** (decision D-004). CPU only; no GPU needed.

```bash
git clone <this repository> fall_monitoring_system
cd fall_monitoring_system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only PyTorch (smaller)
pip install -r requirements.txt
pip install -e .                     # installs the `fallmon` command
fallmon --help
```

### Raw dataset (only for live replays and re-running the evaluation)

Not committed (size). The models, results, logs and dataset index are in the repository, so only fetch it if you need the features marked "with raw data" in section 4.1:

```bash
git clone https://github.com/Fall-Prevention-Team/sisfallData.git data/raw/SisFall_dataset && git -C data/raw/SisFall_dataset checkout 8352a0f
find data/raw/SisFall_dataset -name '*.txt' ! -name 'Readme.txt' | wc -l    # expect 4505
```

Expect **4,505** files (the readme says 4,510; five trials are missing in every known copy, see `doc/dataset_notes.md`). In the thesis, cite the original paper (Sucerquia et al., 2017), not the mirror.

---

## 6. Commands, in order

**You do not need to run these to use the project**: every output is already committed. They document how the results were produced, and are there if something must be regenerated. Every step reads `config/default.yaml`, where all tunable values live. Times are on an 8-core laptop CPU.

| Step | Command | What it does | Time | Main outputs |
|---|---|---|---|---|
| 1 | `fallmon prepare-data` | Indexes all trial files, converts sensor counts to g and °/s, writes the participant-level split (only if it does not exist), plots examples | 10 s | `data/processed/index.parquet`, `data/splits.json`, `results/tables/dataset_summary.md`, `splits_summary.md` |
| 2 | `fallmon train` | Fits the normaliser and trains the three CNNs on **training-subject known activities only**; early stopping on validation | ~26 min | `models/dte_w*.pt`, `scaler.json`, `dte_meta.json`, `results/tables/phase2_*` |
| 3 | `fallmon tune-verifier` | Grid search of 2,430 verifier settings on **validation known activities and falls only** | ~2 min | `models/verifier_config.json`, `results/tables/verifier_*` |
| 4 | `fallmon filter-check` | Causal vs zero-phase filter comparison (validation) | ~1 min | `results/tables/phase4_filter_check.md` |
| 5 | `fallmon batch --split val --mode both` | Replays all validation trials through the live stream processor | ~8 min | `results/tables/phase3_batch_val_*` |
| 6 | `fallmon freeze` | Locks config, models, verifier and split with SHA-256 hashes | 1 s | `results/frozen_config.yaml`, `.sha256` |
| 7 | `fallmon evaluate --split test --all` | **Final evaluation** (refuses unless the freeze matches): E1–E7, demo cases, SUMMARY | ~10 min | `results/tables/e*`, `results/figures/e*`, `results/SUMMARY.md`, `results/demo_cases.json` |

Other commands:

| Command | Use |
|---|---|
| `fallmon stream --trial F05_SA01_R01 --mode both --speed 10` | Watch one trial live in the terminal, baseline and proposed side by side (any trial now that the final evaluation is done; needs raw data) |
| `fallmon demo --case 1 --speed 5` | Replay a demo case (1 fall, 2 unseen fall-like activity, 3 normal activity, 4 failure) |
| `fallmon evaluate --split val --all` | Dry run of the final evaluation on validation, written to `results/dryrun_val/` |
| `fallmon show-config` | Print the validated configuration |
| `streamlit run app/dashboard.py` | The monitoring dashboard (section 4) |
| `pytest` | Run the 76 tests |

### Built-in safety rails
- **Test lock:** before the final evaluation, the test split could not be opened by `stream`, `batch` or the dashboard; `evaluate --split test` refuses unless `results/frozen_config.yaml` matches the current config and model files exactly. Re-freezing after looking at test results would be visible in the hashes.
- **Leakage guards** (`src/fallmon/guards.py`, all unit-tested): no subject in two partitions; training windows contain only known activities from training subjects; the normaliser was fitted on training subjects only; the verifier was tuned on validation known activities and falls only.
- `prepare-data` never overwrites `data/splits.json` unless you pass `--force`; `freeze` and `evaluate --split test` need `--force` / `--rerun` to repeat.

---

## 7. Reproducing the results

**Nothing needs to be regenerated to write the thesis or present**: the final tables, figures, SUMMARY, demo cases and the log database of the official runs are committed.

**To prove the results are reproducible (exact).** With the raw data in place (section 4.1):

```bash
fallmon evaluate --split test --all --rerun
```

The models, frozen configuration, split and dataset index are committed (D-015), so this gives identical numbers under the same frozen hash. This was checked: a second run matched every metric; only run ids and wall-clock processing times differ (X-011 in `doc/experiments_log.md`). It overwrites `results/`; use `git checkout results` to return to the committed files.

**From scratch (full pipeline).** Run all steps in section 6. Retraining is not guaranteed to be bit-identical across machines, so the new models will have different hashes. You must re-tune, re-freeze (`fallmon freeze --force`) and re-evaluate (`--rerun`), and expect small differences from the published numbers.

---

## 8. How it works (detail for Chapter 4)

Config keys are in `code font`; they all live in `config/default.yaml`.

**Data (PRD 5, `data_loader.py`).** SisFall: 23 young (SA01–SA23, 19–30 years) and 15 older (SE01–SE15, 60–75 years) participants, a waist-worn device sampled at 200 Hz, 19 activities of daily living (D01–D19) and 15 fall types (F01–F15). Only the ADXL345 accelerometer and ITG3200 gyroscope are used. Counts are converted with value = [(2 × range) / 2^bits] × raw (±16 g, 13 bits; ±2000 °/s, 16 bits). Activities are grouped (`activities`):
- **known ADLs** (15 codes): used for training;
- **unknown ADLs**: D10 quick sit in a low chair, D11 collapse into a chair, D13 lie down quickly, D18 stumble. These are fall-like activities that no trained or tuned part ever sees; they only appear in the final test;
- **falls** (15 codes): never used for training; they are what OOD detection must catch.

**Preprocessing (PRD 6, `preprocessing.py`).** 4th-order Butterworth low-pass at 20 Hz, causal (the same filter offline and in the stream, so there is no train/serve difference; the filter check showed a ~20 ms delay and no measurable effect), then every 4th sample (50 Hz), then magnitudes Am = |acceleration| (g) and Gm = |rotation| (°/s). The CNNs get z-scored ax, ay, az, gx, gy, gz, Am, Gm; the verifier uses unnormalised physical values.

**Split (PRD 7, `splits.py`).** By participant, seeded: young 15/4/4, older 9/3/3 (train/validation/test). SE06, the only older participant with falls, is forced into test. Stored in `data/splits.json`.

**Baseline Deep Time Ensemble (PRD 8, `dte.py`, `train.py`).** Three identical small 1D-CNNs (three conv layers, global average pooling, dropout 0.3), one each for 1, 2 and 3 s windows. Training labels are 8 coarse activity groups plus a shared **static** class for windows where the person is still (decision D-009; with one label per activity code, still postures shared by many activities made the classifier unsure on almost every normal trial). Every 0.5 s each CNN takes its latest window; softmax outputs are averaged; confidence = highest probability; **OOD if confidence < 0.9** (`ood.threshold`, the value cited in the thesis; the same for both systems).

**Events (PRD 10, `events.py`).** One movement should give at most one alert. An event opens at the first OOD step; OOD steps within 1 s extend it; it closes after 1 s without OOD; an alert starts a 10 s cooldown.

**Proposed verifier (PRD 9, `verifier.py`, `pipeline.py`).** On an event: find the impact (largest Am from 1.5 s before to 1.0 s after the event opened), wait until 1.5 s after the impact (`post_window_s`), then measure the impact peak, the orientation change (angle between average gravity direction 2–1 s before and 1–1.5 s after the impact), post-impact stillness (Am std), and the longest low-activity run. Decision rule (selected by tuning): **impact ≥ 3.0 g AND at least 2 of {orientation ≥ 30°, Am std ≤ 0.12 g, low activity ≥ 1.0 s}**. If rejected, the event ends and later impacts get their own check (**re-arm**, D-012; without it no setting reached 95% fall recall on validation, because events often open during the activity before the fall).

**Tuning (PRD 9.5, `tune_verifier.py`).** All 2,430 combinations of the grid in `verifier.grid` were tried on validation known activities and falls. Chosen: lowest validation false-alert rate with validation fall recall ≥ 0.95.

**Evaluation (PRD 13, `evaluation.py`).** Every test trial is replayed through the real stream processor in both modes. Sensitivity = alerted fall trials / fall trials; FPR = alerted trials / trials of that group; precision = alerted fall trials / alerted trials; false alerts per hour = alerts in non-fall trials / hours of non-fall recording; decision delay = first alert − time of the largest Am in the fall trial. 95% bootstrap CIs (1,000 resamples over trials); exact McNemar tests on paired outcomes. Experiments:

| ID | Question | Files |
|---|---|---|
| E1 | How well does the DTE recognise known activities? | `e1_classification.md`, `e1_confusion_matrix.png` |
| E2 | How well does confidence alone separate normal from fall/unknown? | `e2_ood.md`, `e2_ood_rates.md`, `e2_confidence_hist_by_group.png`, `e2_roc.png` |
| E3 | How does the verifier decide on the events it sees? | `e3_verifier.md`, `e3_confusion.png`, `e3_verifier_features_by_group.png` |
| E4 | Baseline vs proposed, end to end (headline) | `e4_end_to_end.md`, `e4_calibrated_threshold.md`, `e4_baseline_vs_proposed.png` |
| E5 | Effect of the post-window length (reporting only) | `e5_sweep.md`, `e5_post_window_tradeoff.png` |
| E6 | Young vs older; each unknown activity | `e6_subgroups.md`, `e6_unknown_adl_by_code.md`, `e6_unknown_adl_breakdown.png` |
| E7 | Processing latency | `e7_latency.md`, `e7_latency.png` |
| Demo | Illustrative cases chosen by fixed rules | `demo_case_*.png`, `demo_cases.json` |

---

## 9. Project structure

```
config/default.yaml        every tunable value (validated by src/fallmon/config.py)
data/splits.json           participant split
data/processed/            dataset index (index.parquet)
data/raw/SisFall_dataset/  raw dataset: NOT committed; download command in section 4.1
models/                    trained CNNs, scaler, metadata, selected verifier (committed)
  as_specified/            first DTE run with per-activity labels (kept for D-009)
results/
  SUMMARY.md               final headline numbers and failure cases
  tables/, figures/        all tables (CSV + Markdown) and figures (300 dpi PNG)
  frozen_config.yaml/.sha256   the locked setup
  dryrun_val/              validation dry run of the evaluation (not results)
logs/fallmon.db            SQLite: all runs incl. the official test runs; activity / unknown-activity / alert logs, events
src/fallmon/               the package: data_loader, preprocessing, splits, windowing, dte, train, ood,
                           events, verifier, tune_verifier, pipeline, stream_simulator, storage, notifier,
                           evaluation, guards, filter_check, dashboard_data, reporting, cli
app/dashboard.py           Streamlit dashboard
tests/                     76 tests, including leakage guards and the test lock
doc/                       thesis documentation (start with doc/README.md)
fall-monitoring-PRD.md     the original specification
```

---

## 10. Decisions that changed the original plan

Full reasoning is in `doc/decisions_log.md`. The ones an examiner is most likely to ask about:

| ID | Change | Why |
|---|---|---|
| D-007 | Baseline reimplemented from the paper | No official code from Roy et al. exists |
| D-009 | Coarse activity groups + "static" class as DTE labels | With per-code labels, 99% of normal validation trials looked OOD |
| D-011 | Baseline also reported at a calibrated threshold (0.49) | Shows the result does not depend on the baseline's 0.9 threshold |
| D-012 | Re-arm after a rejected verification | Without it, no setting kept 95% fall recall on validation |
| D-013 | Rest rule reported as inactive | With a 1.5 s post window it cannot be satisfied |
| D-014 | Console-only notifications | Email and Telegram removed from scope |
| D-015 | Model weights committed | Lets a clean clone reproduce the frozen results |

Smaller ones: Python 3.10 (D-004); subject taken from the folder because of mislabelled SA15 files (D-005); training stride 0.24 s (D-008); implementation details (D-010); configurable feature windows (D-013).

---

## 11. Known limitations

The full list, with numbers, is in `doc/limitations.md`. The essentials:

- **Simulated, not real.** Lab-simulated falls by mostly young volunteers, replayed from a dataset. No real device, older-adult falls, battery or network effects.
- **Few subjects.** 7 test subjects; results depend strongly on individuals (two subjects account for 60 of 74 missed falls). Older-adult falls come from one person (SE06, a judo expert).
- **Sensitivity loss.** The impact threshold chosen on validation (3.0 g) was too high for softer falls; test sensitivity 0.803 vs 0.960 on validation.
- **Remaining false alerts are fall-like.** 5 of the 6 are "collapse into a chair" (D11).
- **Delay.** The proposed alert comes about 1.9 s after the impact, because it waits for post-impact evidence.
- **Modified baseline.** Coarse labels (D-009) instead of Roy et al.'s per-activity labels; the baseline is weak per trial (it alerts on almost every normal trial), which makes the false-alert reduction look large. Per-step rates (E2) are closer to how OOD papers report.
- **Rest rule inactive** in the selected configuration (D-013).

---

## 12. Tests

```bash
pytest          # 76 tests, ~20 s
```

They cover: file parsing quirks and unit conversion; stream preprocessing equal to offline; split sizes, determinism and SE06 rule; all four leakage guards; windowing and labelling; CNN shapes and ensemble averaging; event merge/close/cooldown; baseline and proposed decisions on synthetic signals (a fall verifies, a hard sit-down is rejected, re-arm catches a fall inside an early event); stream processor equal to the tuning replay; freeze and test lock; metric formulas; and the dashboard (a full side-by-side replay through Streamlit's test harness, and the message shown when the raw data is missing).

---

## 13. Glossary

| Term | Meaning here |
|---|---|
| ADL | Activity of daily living (walking, sitting down, lying down, …) |
| Known ADL | An ADL used to train the classifier |
| Unknown ADL | A fall-like ADL never seen by any trained or tuned part (D10, D11, D13, D18) |
| OOD | Out of distribution: the classifier's confidence is below 0.9, so the movement looks unfamiliar |
| DTE | Deep Time Ensemble: the three CNNs on 1, 2 and 3 s windows (Roy et al., 2023) |
| Decision step | One classifier decision, every 0.5 s |
| Event | A run of OOD steps treated as one movement |
| HOLD | Proposed mode: the alert is held while the verifier waits for post-impact data |
| VERIFIED / REJECTED | Verifier outcome: alert raised / no alert (logged as unknown activity) |
| Re-arm | After a rejection the event ends, so a later impact can be checked separately |
| Cooldown | 10 s after an alert during which no new event opens |
| Am, Gm | Magnitude of acceleration (g) and of rotation (°/s) |
| Sensitivity | Share of fall trials with an alert |
| FPR | False-positive rate: share of non-fall trials (of a group) with an alert |
| Decision delay | First alert time minus the impact time (largest Am) in a fall trial |
| Bootstrap CI | Range of a metric over 1,000 random resamples of the trials (95%) |
| McNemar test | Significance test comparing two systems on the same trials |
| Frozen hash | SHA-256 fingerprint of the locked config and models used for the final results |
| Validation / test split | Subjects used for choosing settings / subjects held back for the final, one-time evaluation |

---

## 14. References

- Sucerquia, A., López, J. D., & Vargas-Bonilla, J. F. (2017). SisFall: A fall and movement dataset. *Sensors*, 17(1), 198. https://doi.org/10.3390/s17010198
- Roy, D., Komini, V., & Girdzijauskas, S. (2023). Classifying falls using out-of-distribution detection in human activity recognition. *AI Communications*, 36(4), 251–267. https://doi.org/10.3233/AIC-220205
