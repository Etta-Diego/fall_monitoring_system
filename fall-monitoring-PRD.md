# PRD: Fall Monitoring System with Post-Event Temporal Verification

**Project:** Design and Development of an Enhanced IoT-Based System for Reliable Real-Time Fall Classification and Alert Verification in Elderly Care
**Type:** Academic thesis software artefact (software-only, simulated IoT stream)
**Audience:** Claude Code (implementation agent) and the developer
**Status:** Ready for build

---

## 0. How to use this document (instructions for Claude Code)

1. Build **phase by phase** (Section 14). Finish a phase, run its acceptance checks, then stop and report results before starting the next phase.
2. **Never touch the test split** until Phase 6. No threshold, hyperparameter, window size or rule may be chosen using test data. Section 11 lists the guards you must implement.
3. Where this document says **VERIFY**, check the actual dataset files or official SisFall readme before coding. Do not assume.
4. Prefer simple, readable code over clever code. This is a thesis artefact: an examiner may read it.
5. Every configurable value lives in `config/default.yaml`. No magic numbers in source.
6. Never write text, logs, UI labels or notification content that implies physical hardware, a real wearable, or real elderly falls. Section 2.3 has the exact wording rules.

---

## 1. Background and goal

### 1.1 What the thesis claims
The thesis (Chapters 1 to 3) adopts **Roy et al. (2023)** as the existing system. Roy et al. train a Deep Time Ensemble (DTE) of CNNs on **non-fall activities only**. At run time, the ensemble's maximum softmax probability is the confidence score. Low confidence means out-of-distribution (OOD), and OOD is treated as a **probable fall that triggers an alarm directly**.

The identified gap (Section 2.5 of the thesis): there is **no post-event verification** between OOD detection and alarm. Unfamiliar non-fall activities also produce low confidence and therefore false alarms.

### 1.2 What this software must demonstrate
The proposed system inserts a **post-event temporal verification** stage:

```
OOD event detected  ->  hold  ->  examine windows around/after the event
                                   |-> VERIFIED FALL  -> alert + alert log
                                   |-> REJECTED       -> unknown activity log (no alert)
```

The contribution is this verification stage. Everything else reproduces existing work as faithfully as practical so the comparison is fair.

### 1.3 Primary research question the software answers
> Compared with the Roy et al. style baseline, how much does post-event temporal verification reduce false alerts (especially on unseen fall-like ADLs), and what does it cost in genuine-fall sensitivity and decision delay?

---

## 2. Scope

### 2.1 In scope
- SisFall data loader, unit conversion, preprocessing.
- Participant-level train/validation/test split, saved and reproducible.
- Baseline: Deep Time Ensemble reimplementation (3 small 1D-CNNs, different window lengths), max-softmax confidence, fixed threshold.
- Proposed: same DTE plus rule-based post-event temporal verification.
- Shared event logic (merge OOD steps into events, cooldown).
- Real-time stream simulator (sample-by-sample replay, configurable speed).
- SQLite logging: activity log, unknown activity log, alert log, event decision trace.
- Alert notifier: console (always), email via SMTP (optional), Telegram bot (optional).
- Streamlit monitoring dashboard.
- Full evaluation pipeline producing tables and figures for Chapter 4.
- CLI for every step.
- Unit tests, including leakage guards.

### 2.2 Out of scope (do not build)
- Any physical hardware, firmware, ESP32, Raspberry Pi, BLE, MQTT broker.
- XAI / SHAP / LIME (not in the thesis objectives).
- Fall class in classifier training (falls are OOD by design).
- Deep-learning verifier, transformer models, or any "better classifier" replacing the pipeline.
- User accounts, authentication, cloud deployment.
- Model retraining from feedback.

### 2.3 Honesty rules (hard requirements)
- All UI, logs, README and notifications must describe the data source as **"SisFall dataset replay (simulated IoT stream)"**.
- Notification subject/prefix must include `[SIMULATED]`.
- Never label SisFall falls as "elderly falls". SisFall falls were performed by young volunteers (plus one older participant, VERIFY: SE06). Use "simulated falls from SisFall".
- Report results exactly as computed, including failure cases. No cherry-picking trials for headline metrics.

---

## 3. Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Deep learning | PyTorch (CPU only is fine) |
| Classical / metrics | scikit-learn, scipy, numpy, pandas |
| Stats | scipy.stats (McNemar via statsmodels if needed) |
| Config | PyYAML + pydantic for validation |
| CLI | Typer |
| Storage | SQLite (stdlib `sqlite3`) |
| Dashboard | Streamlit + Plotly |
| Plots for thesis | matplotlib (PNG, 300 dpi) |
| Tests | pytest |
| Env | `requirements.txt`, `.env` for secrets (`.env.example` committed) |

Set global seeds (Python, numpy, torch) from config. Use `torch.use_deterministic_algorithms(True)` where it does not break ops.

---

## 4. Repository structure

```
fall_monitoring_system/
├── README.md
├── PRD.md
├── requirements.txt
├── .env.example
├── config/
│   └── default.yaml
├── data/
│   ├── raw/SisFall_dataset/        # user places dataset here (gitignored)
│   ├── processed/                  # parquet/npz caches (gitignored)
│   └── splits.json                 # committed once generated
├── models/                         # trained weights, scalers (gitignored except metadata)
├── results/
│   ├── tables/                     # CSV + markdown tables
│   ├── figures/                    # PNG figures for Chapter 4
│   ├── frozen_config.yaml          # written at end of Phase 5
│   └── frozen_config.sha256
├── logs/
│   └── fallmon.db                  # SQLite
├── src/fallmon/
│   ├── __init__.py
│   ├── config.py                   # pydantic models, load/validate yaml
│   ├── data_loader.py              # parse SisFall files, unit conversion
│   ├── preprocessing.py            # filter, downsample, magnitudes, normalisation
│   ├── splits.py                   # participant-level split + leakage checks
│   ├── windowing.py                # sliding windows for training
│   ├── dte.py                      # CNN model, ensemble wrapper
│   ├── train.py                    # training loop
│   ├── ood.py                      # confidence scoring, thresholding
│   ├── events.py                   # OOD step -> event aggregation, cooldown
│   ├── verifier.py                 # temporal verification features + rules
│   ├── tune_verifier.py            # grid search on validation only
│   ├── pipeline.py                 # StreamProcessor: baseline / proposed modes
│   ├── stream_simulator.py         # sample-by-sample replay
│   ├── storage.py                  # SQLite schema + writes
│   ├── notifier.py                 # console / email / telegram
│   ├── evaluation.py               # metrics, stats, tables, figures
│   ├── guards.py                   # test-lock + leakage assertions
│   └── cli.py                      # Typer app
├── app/
│   └── dashboard.py                # Streamlit
├── notebooks/                      # optional exploration only, never imported by src
└── tests/
    ├── test_data_loader.py
    ├── test_splits.py
    ├── test_windowing.py
    ├── test_events.py
    ├── test_verifier.py
    ├── test_pipeline.py
    └── test_guards.py
```

---

## 5. Dataset specification (SisFall)

### 5.1 Facts to rely on (VERIFY each against the readme and files)
- Folder per subject: young `SA01` to `SA23`, elderly `SE01` to `SE15`.
- File name pattern: `<ACTIVITY>_<SUBJECT>_R<TRIAL>.txt`, e.g. `F05_SA12_R03.txt`.
- Each line: 9 comma-separated integers, line ends with `;`. Columns:
  - 1 to 3: ADXL345 accelerometer X, Y, Z
  - 4 to 6: ITG3200 gyroscope X, Y, Z
  - 7 to 9: MMA8451Q accelerometer X, Y, Z (**ignore**)
- Sampling rate: 200 Hz.
- Activities: **19 ADLs (D01 to D19)** and **15 falls (F01 to F15)**.
- Elderly participants mostly performed ADLs only, and not every ADL. Discover the actual set of available files per subject; do not assume completeness.

### 5.2 Unit conversion (VERIFY constants in SisFall readme)
```
acc_g   = ((2 * range_g)   / (2 ** resolution_bits)) * raw     # ADXL345: range 16 g, 13 bits
gyro_dps = ((2 * range_dps) / (2 ** resolution_bits)) * raw    # ITG3200: range 2000 deg/s, 16 bits
```
Put ranges and bit resolutions in config under `dataset.sensors`.

### 5.3 Activity groups (config driven)
```yaml
activities:
  known_adls:   [D01, D02, D03, D04, D05, D06, D07, D08, D09, D12, D14, D15, D16, D17, D19]
  unknown_adls: [D10, D11, D13, D18]
  falls:        [F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15]
```
Rationale: unknown ADLs are fall-like and never seen by any trained or tuned component. D08, D12, D14, D19 stay known so the verifier can be tuned against abrupt but known movements.

### 5.4 Loader output
`load_trial(path) -> Trial` dataclass:
```
subject_id: str        # "SA12"
age_group: str         # "young" | "elderly"
activity_code: str     # "F05"
activity_group: str    # "known_adl" | "unknown_adl" | "fall"
trial_no: int
fs: int                # 200 (raw)
data: np.ndarray       # shape (n, 6): ax, ay, az [g], gx, gy, gz [deg/s]
```
`build_index(raw_dir) -> pd.DataFrame` with one row per file (subject, activity, trial, group, n_samples, duration_s, path). Save to `data/processed/index.parquet`. Print a summary table of trials per group per age group.

Temporal order within a trial must never be shuffled.

---

## 6. Preprocessing

Applied identically in training and streaming. Order:

1. **Low-pass filter**: 4th-order Butterworth, cutoff `preprocessing.lowpass_hz` (default 20 Hz). Offline use `filtfilt`. In streaming use a causal `lfilter` with persistent state (`sosfilt` + `zi`). Document this difference; offline training on filtfilt vs causal streaming must be checked in Phase 4 (see 6.1).
2. **Downsample** 200 Hz to `preprocessing.target_fs` (default 50 Hz) by decimation after filtering (factor 4).
3. **Derived channels**:
   - `Am = sqrt(ax^2 + ay^2 + az^2)` in g
   - `Gm = sqrt(gx^2 + gy^2 + gz^2)` in deg/s
4. Model input channels (default 8): `ax, ay, az, gx, gy, gz, Am, Gm`.
5. **Normalisation**: per-channel z-score. Fit `mean, std` on **training split known-ADL windows only**. Save to `models/scaler.json`. Apply everywhere.

The verifier (Section 9) uses **unnormalised** filtered signals in physical units (g, deg/s).

### 6.1 Filter consistency
Default decision: use the **causal filter for both training and streaming** so there is zero train/serve skew. Keep `filtfilt` as a config option (`preprocessing.offline_zero_phase: false`). Do not switch the default without reporting the effect.

---

## 7. Data split

### 7.1 Rules
- Split by **participant**. A subject appears in exactly one partition.
- Defaults (configurable, seeded):
  - Young (23): train 15, val 4, test 4
  - Elderly (15): train 9, val 3, test 3
  - If SE06 (or whichever elderly subject has fall files, VERIFY) exists, force it into **test** and log that decision.
- Write `data/splits.json`:
```json
{
  "seed": 42,
  "created_at": "...",
  "train": ["SA01", "..."],
  "val":   ["SA16", "..."],
  "test":  ["SA20", "..."],
  "notes": "SE06 forced to test (only elderly subject with falls)"
}
```
- Once `splits.json` exists, never regenerate unless `--force` is passed. Commit it.

### 7.2 What each partition is used for
| Partition | Known ADLs | Unknown ADLs | Falls |
|---|---|---|---|
| Train | Train CNNs, fit scaler | **Not used** | **Not used** |
| Val | Early stopping, verifier tuning | **Not used** | Verifier tuning |
| Test | Final eval | Final eval | Final eval |

Unknown ADLs from **all** partitions are excluded from training and tuning. They appear only in the test evaluation (Phase 6).

---

## 8. Baseline: Deep Time Ensemble (Roy et al. 2023 reimplementation)

Before implementing, search for an official code release of Roy et al. (2023). If one exists, adapt it and document differences. If not, implement as below and state in README that it is a reimplementation from the paper's description.

### 8.1 Windows for training
- Window lengths (seconds): `dte.window_lengths_s: [1.0, 2.0, 3.0]` (50, 100, 150 samples at 50 Hz).
- Training stride: `dte.train_stride_s: 0.25`.
- Windows come from **known-ADL trials of train subjects only**. Label = activity code (multi-class, 15 classes by default).
- Class imbalance: D01 to D04 are long trials. Use a `WeightedRandomSampler` or cap windows per (subject, activity) at `dte.max_windows_per_trial`.

### 8.2 Model (one per window length)
```
Conv1d(in=8, out=32, k=5, pad=2) -> BatchNorm -> ReLU
Conv1d(32, 64, k=5, pad=2)       -> BatchNorm -> ReLU -> MaxPool(2)
Conv1d(64, 64, k=3, pad=1)       -> BatchNorm -> ReLU
GlobalAveragePooling1d
Dropout(0.3)
Linear(64, n_classes)
```
- Optimiser Adam, lr 1e-3, weight decay 1e-4, batch 128, max 40 epochs.
- Early stopping on validation **macro F1 over known ADLs**, patience 6.
- Save `models/dte_w{len}.pt` + `models/dte_meta.json` (class list, window lengths, channels, scaler path, git hash, val metrics).

### 8.3 Ensemble inference and confidence
At each decision step `t` (stride `stream.decision_stride_s`, default 0.5 s):
- Each model receives the latest window of its own length ending at `t`.
- `p_ens = mean(softmax_k)` over the 3 models.
- `confidence = max(p_ens)`; `predicted_activity = argmax(p_ens)`.
- First decision only once the longest window is filled (3 s).

### 8.4 OOD decision
- `is_ood = confidence < ood.threshold`, default **0.9** (value cited in thesis 2.1.8).
- Same threshold for baseline and proposed. This keeps the comparison fair.
- Also compute `ood_score = 1 - confidence` for AUROC reporting.
- Additionally report (not used for decisions) the threshold that gives 95% TPR on validation known ADLs, as a sensitivity note.

---

## 9. Proposed: post-event temporal verification

### 9.1 Trigger
Only runs in `mode=proposed`, once per **event** (Section 10), not per step.

### 9.2 Impact localisation
On event open at time `t_e`:
- Search `Am` (filtered, physical units) in `[t_e - verifier.impact_search_pre_s, t_e + verifier.impact_search_post_s]` (defaults 1.5 s, 1.0 s).
- `t_impact = argmax(Am)` in that range.
- Verification waits until `t_impact + verifier.post_window_s` (default 2.0 s) has arrived in the stream, then evaluates. If the trial ends first, evaluate with available data and set `truncated = true`.

### 9.3 Features (all physical units)
| Feature | Definition |
|---|---|
| `impact_peak_g` | max `Am` in `[t_impact - 0.5, t_impact + 0.5]` |
| `gyro_peak_dps` | max `Gm` in `[t_impact - 0.5, t_impact + 0.5]` |
| `orientation_change_deg` | angle between mean acc vector in pre interval `[t_impact - 2.0, t_impact - 1.0]` and post interval `[t_impact + 1.0, t_impact + post_window_s]` |
| `post_am_std_g` | std of `Am` in post interval |
| `post_gm_mean_dps` | mean of `Gm` in post interval |
| `low_activity_s` | longest continuous run in post interval where rolling (0.5 s) std of `Am` < `verifier.still_std_g` |

Interval offsets go in config. If the pre interval falls before trial start, use what is available and flag `pre_truncated`.

### 9.4 Rules
Each rule is a boolean:
```
R_impact  = impact_peak_g          >= T_impact
R_orient  = orientation_change_deg >= T_orient
R_still   = post_am_std_g          <= T_still
R_rest    = low_activity_s         >= T_rest
```
Combination modes (config `verifier.combine`):
- `"impact_and_any"`: `R_impact AND (R_orient OR R_still OR R_rest)`
- `"impact_and_k_of_3"`: `R_impact AND count(R_orient, R_still, R_rest) >= k`
- `"all"`: all four true

Output:
```python
@dataclass
class VerificationResult:
    verified: bool
    features: dict[str, float]
    rules: dict[str, bool]
    t_impact: float
    truncated: bool
    reason: str   # human readable, e.g. "impact 3.1g >= 2.5g; orientation 74deg >= 45deg -> VERIFIED"
```

### 9.5 Tuning (validation only)
`tune_verifier.py`:
1. Run the proposed pipeline in **offline batch mode** over validation subjects' **known-ADL and fall** trials (never unknown ADLs).
2. Collect every event that reaches the verifier, with its features and ground-truth group.
3. Grid search over `T_impact, T_orient, T_still, T_rest`, `combine`, `k`, and `post_window_s` (grid defined in config).
4. Objective: **minimise false-alert rate on validation known ADLs subject to validation fall recall >= `verifier.min_fall_recall` (default 0.95)**. Tie-break: shorter `post_window_s`, then simpler combine mode.
5. Save chosen config to `models/verifier_config.json` and full grid results to `results/tables/verifier_grid_val.csv`.

If no configuration meets the recall constraint, report it and pick the configuration with highest recall. Do not silently relax.

---

## 10. Event logic (shared by both modes)

Purpose: one physical movement produces at most one alert. Metrics are event/trial level.

- An **event opens** at the first OOD decision step when no event is open and no cooldown is active.
- OOD steps within `events.merge_gap_s` (default 1.0 s) of the last OOD step extend the event.
- The event **closes** when no OOD step occurs for `events.merge_gap_s`.
- After an alert, a **cooldown** of `events.cooldown_s` (default 10 s) suppresses new events for that stream.

Mode behaviour on event open:
- `baseline`: immediately emit `ALERT` (probable fall), as in Roy et al.
- `proposed`: emit `HOLD`, run verification when post window is available, then emit `ALERT` or `REJECTED`.

Known (non-OOD) steps write to the activity log, rate limited: write one row per `logging.activity_log_interval_s` (default 2 s) with the majority predicted activity, to keep the DB small.

---

## 11. Leakage guards and test lock (`guards.py`)

Implement and unit test:
1. `assert_no_subject_overlap(splits)`.
2. `assert_no_unknown_in_training(train_windows_index)`: no unknown ADL or fall code in any training window.
3. `assert_scaler_fit_on_train(scaler_meta, splits)`.
4. `assert_verifier_tuned_without_test_or_unknown(tuning_index)`.
5. **Test lock**:
   - `fallmon freeze` writes `results/frozen_config.yaml` (merged config + model hashes + verifier config) and its SHA-256.
   - `fallmon evaluate --split test` refuses to run unless the frozen file exists and its hash matches the current config + models. Print a clear error otherwise.
   - Test evaluation results include the frozen hash in every output file header.

---

## 12. Runtime components

### 12.1 Stream simulator (`stream_simulator.py`)
```python
class StreamSimulator:
    def __init__(self, trials: list[Trial], speed: float = 1.0, realtime: bool = True): ...
    def __iter__(self) -> Iterator[Sample]   # Sample(t_s, raw_6ch, trial_id, subject_id)
```
- Emits raw 200 Hz samples one at a time, in order.
- `speed`: 1.0 = wall-clock 200 Hz, 10 = 10x faster. `realtime=False` = as fast as possible (evaluation).
- Can chain multiple trials with `gap_s` of synthetic silence in between? **No.** Do not fabricate data. Chain trials back to back and reset all filter/buffer/event state at each trial boundary.

### 12.2 Stream processor (`pipeline.py`)
```python
class StreamProcessor:
    def __init__(self, mode: Literal["baseline", "proposed"], cfg, models, storage, notifier): ...
    def push(self, sample: Sample) -> list[Decision]
    def reset(self): ...
```
- Holds causal filter state, decimation counter, ring buffers (raw physical units and normalised), event state machine, pending verifications.
- Every decision step measures **processing latency** (time from receiving the sample that completes the step to the decision being produced) with `time.perf_counter()`.
- `Decision` record:
```
t_s, trial_id, subject_id, mode,
predicted_activity, confidence, is_ood,
event_id | None, status in {KNOWN, HOLD, ALERT, REJECTED},
verification: VerificationResult | None,
latency_ms
```

### 12.3 Storage (`storage.py`, SQLite)
Tables:
```sql
runs(run_id TEXT PK, created_at, mode, split, frozen_hash, config_json)
activity_log(id PK, run_id, t_s, subject_id, trial_id, activity, confidence)
events(event_id TEXT PK, run_id, mode, subject_id, trial_id, t_open_s, t_impact_s,
       t_decision_s, min_confidence, status, reason, features_json, rules_json,
       truncated INT, decision_delay_s, latency_ms)
unknown_activity_log(id PK, run_id, event_id, t_s, subject_id, trial_id, reason)
alert_log(id PK, run_id, event_id, t_s, subject_id, trial_id, mode, channel, delivered INT, message)
```
Every event row must contain a human-readable `reason` explaining why it was alerted, held or rejected.

### 12.4 Notifier (`notifier.py`)
- `ConsoleNotifier` always on.
- `EmailNotifier` (SMTP, env vars `SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO`).
- `TelegramNotifier` (env `TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID`).
- Enabled via config `notifier.channels`. Failures are logged, never crash the stream.
- Message template:
```
[SIMULATED] Verified fall alert
Source: SisFall replay (simulated IoT stream)
Subject: SA20 | Trial: F05_SA20_R01
Time in trial: 7.42 s
Reason: impact 3.1 g; orientation change 74 deg; low activity 1.8 s
```
- Notifications are **disabled during batch evaluation** (`notifier.enabled_in_eval: false`).

### 12.5 Dashboard (`app/dashboard.py`, Streamlit)
Header banner always visible: "Data source: SisFall dataset replay (simulated IoT stream). No physical device."

Pages:
1. **Live Replay**: pick subject, trial, mode (baseline / proposed / side by side), speed. Show stream status, current predicted activity, confidence gauge, OOD flag, verification status, final decision, alert status. Rolling Plotly chart of `Am` and `Gm` (last 10 s) with markers for event open, impact, decision.
2. **Event Details**: select event, show confidence, features table, each rule pass/fail with threshold, final decision and reason, decision delay, latency.
3. **Logs**: tabs for activity log, unknown activity log, alert log; filters by run, mode, subject.
4. **Results**: render tables and figures from `results/` (read-only).

Side-by-side mode runs two `StreamProcessor`s on the same sample stream.

---

## 13. Evaluation (`evaluation.py`)

### 13.1 Ground truth
Per trial: `fall`, `known_adl`, `unknown_adl`. Reference impact time for fall trials: `argmax(Am)` over the full filtered trial (used only for decision-delay reporting).

### 13.2 Trial-level outcome
A trial is **alerted** if the system produced at least one `ALERT` in it.

### 13.3 Metrics (computed for baseline and proposed, same test trials)
| Metric | Definition |
|---|---|
| Sensitivity / recall | alerted fall trials / fall trials |
| Specificity | non-alerted non-fall trials / non-fall trials |
| Precision | alerted fall trials / all alerted trials |
| F1 | from precision and recall |
| Accuracy | (TP + TN) / all trials |
| FPR (known) | alerted known-ADL trials / known-ADL trials |
| FPR (unknown) | alerted unknown-ADL trials / unknown-ADL trials |
| False alerts per hour | total false alerts / total hours of non-fall recording |
| False-alert reduction | (FA_baseline - FA_proposed) / FA_baseline |
| Decision delay | alert time - reference impact time (fall trials), mean, median, p95 |
| Processing latency | per decision step, mean and p95 ms |

Uncertainty and significance:
- 95% bootstrap CIs (1000 resamples over trials, seeded) for sensitivity, FPRs, precision, F1.
- **McNemar's test** on paired trial outcomes (baseline vs proposed), separately for falls and non-falls.

### 13.4 Experiments
| ID | Name | Split | Output |
|---|---|---|---|
| E1 | Known ADL recognition (DTE) | test known ADLs | accuracy, macro F1, per-class report, confusion matrix |
| E2 | OOD detection | test | AUROC/AUPRC for known vs (falls + unknown ADLs), also known vs falls and known vs unknown separately; confidence histograms per group (like thesis Fig 2.8) |
| E3 | Verifier stage alone | test events reaching verifier | confusion matrix (fall vs non-fall), per-rule pass rates per group, feature distribution plots |
| E4 | End-to-end baseline vs proposed | test | headline table (13.3), McNemar, CIs, bar chart |
| E5 | Post-window sensitivity | test, **reporting only** | sweep `post_window_s` in {1.0, 1.5, 2.0, 3.0, 4.0} with other params frozen: FPR vs sensitivity vs delay. Label clearly: "not used for model selection" |
| E6 | Subgroup breakdown | test | E4 metrics split by young vs elderly and by unknown ADL code (D10, D11, D13, D18) |
| E7 | Latency | test stream run | latency distribution plot, mean/p95 per mode |

### 13.5 Required figures (`results/figures/`, 300 dpi PNG)
- `e1_confusion_matrix.png`
- `e2_confidence_hist_by_group.png`, `e2_roc.png`
- `e3_verifier_features_by_group.png`, `e3_confusion.png`
- `e4_baseline_vs_proposed.png` (grouped bars: sensitivity, FPR known, FPR unknown, precision)
- `e5_post_window_tradeoff.png`
- `e6_unknown_adl_breakdown.png`
- `e7_latency.png`
- `demo_case_fall.png`, `demo_case_unknown_adl.png`, `demo_case_known_adl.png`: signal traces with event, impact and decision annotations, baseline vs proposed (Section 15)

### 13.6 Required tables (`results/tables/`, CSV + Markdown)
`e1_classification.md`, `e2_ood.md`, `e3_verifier.md`, `e4_end_to_end.md`, `e5_sweep.md`, `e6_subgroups.md`, `e7_latency.md`, `splits_summary.md`, `dataset_summary.md`, `verifier_selected_config.md`.

---

## 14. Build phases and acceptance criteria

### Phase 1: Data foundation
Build `config.py`, `data_loader.py`, `preprocessing.py`, `splits.py`, CLI `prepare-data`.
**Accept when:**
- Index built; dataset summary printed and saved (trials per group per age group).
- Conversion verified against readme; spot-check one standing-still segment has `Am` near 1 g.
- `splits.json` written; `test_splits.py` passes (no overlap, SE06 rule applied).
- Plots of 1 fall, 1 known ADL, 1 unknown ADL saved to `results/figures/phase1_examples.png`.

### Phase 2: Baseline DTE
Build `windowing.py`, `dte.py`, `train.py`, `ood.py`, CLI `train`.
**Accept when:**
- 3 models trained; val macro F1 reported per model and ensemble.
- Guard 2 and 3 pass.
- Validation confidence histogram for known ADLs vs falls saved (sanity check that falls skew lower).

### Phase 3: Event logic and stream
Build `events.py`, `stream_simulator.py`, `pipeline.py` (baseline mode), `storage.py`, `notifier.py` (console), CLI `stream`.
**Accept when:**
- `fallmon stream --trial F05_SA01_R01 --mode baseline --speed 20` prints decisions and writes DB rows.
- `test_events.py` covers merge, close, cooldown.
- Batch mode over validation runs end to end and reports per-step latency.

### Phase 4: Verifier
Build `verifier.py`, proposed mode in `pipeline.py`, `tune_verifier.py`, CLI `tune-verifier`.
**Accept when:**
- Unit tests with synthetic signals: clear fall-shaped signal verifies, sit-down-shaped signal rejects.
- Grid search runs on validation only (guard 4 passes); selected config saved with its val recall and val FPR.
- Causal vs zero-phase filter check reported (Section 6.1).

### Phase 5: Dashboard, notifier channels, freeze
Build `app/dashboard.py`, email/telegram notifiers, CLI `freeze`.
**Accept when:**
- Dashboard runs with `streamlit run app/dashboard.py`; side-by-side mode works on a validation trial.
- Email or Telegram test message sends with `[SIMULATED]` prefix (if credentials provided).
- `fallmon freeze` writes frozen config + hash.
- **Stop and report. Developer confirms before Phase 6.**

### Phase 6: Final evaluation (test split unlocked)
Build `evaluation.py`, CLI `evaluate`.
**Accept when:**
- All E1 to E7 tables and figures generated from a single command: `fallmon evaluate --split test --all`.
- Every output file header carries the frozen hash.
- `results/SUMMARY.md` auto-generated: headline numbers, CIs, McNemar p-values, notable failure cases (list unknown ADL trials the proposed system still alerted on, and falls it missed).

### Phase 7: Documentation
**Accept when** README contains: purpose, honesty statement, setup, dataset placement, every CLI command in order, how to reproduce results, how to run the dashboard, known limitations.

---

## 15. Demo scenarios (must be reproducible via CLI and dashboard)

Pick real trial IDs from the **test** split after Phase 6 and record them in `results/demo_cases.json`.

1. **Genuine fall**: baseline ALERT; proposed OOD -> HOLD -> VERIFIED -> ALERT.
2. **Unseen fall-like ADL** (e.g. D10): baseline ALERT (false alarm); proposed OOD -> HOLD -> REJECTED -> unknown activity log.
3. **Known ADL** (e.g. D01): both systems KNOWN, no event.
4. **Failure case** (if any exists): an unknown ADL the proposed system still alerted on, or a missed fall. Shown honestly.

CLI: `fallmon demo --case 1 --speed 5` replays the case side by side.

---

## 16. CLI summary

```
fallmon prepare-data            # index, convert, split
fallmon train                   # DTE models + scaler
fallmon tune-verifier           # grid search on validation
fallmon stream --trial ID --mode baseline|proposed|both --speed N
fallmon batch --split val --mode both
fallmon freeze                  # lock config + models
fallmon evaluate --split test --all
fallmon demo --case N --speed N
```

---

## 17. Default config (`config/default.yaml`)

```yaml
seed: 42

dataset:
  raw_dir: data/raw/SisFall_dataset
  fs_raw: 200
  sensors:
    adxl345: {range_g: 16, bits: 13}     # VERIFY
    itg3200: {range_dps: 2000, bits: 16} # VERIFY

activities:
  known_adls:   [D01, D02, D03, D04, D05, D06, D07, D08, D09, D12, D14, D15, D16, D17, D19]
  unknown_adls: [D10, D11, D13, D18]
  falls:        [F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15]

split:
  young:   {train: 15, val: 4, test: 4}
  elderly: {train: 9,  val: 3, test: 3}
  force_test: [SE06]   # VERIFY which elderly subject has falls

preprocessing:
  lowpass_hz: 20
  filter_order: 4
  target_fs: 50
  offline_zero_phase: false
  channels: [ax, ay, az, gx, gy, gz, Am, Gm]

dte:
  window_lengths_s: [1.0, 2.0, 3.0]
  train_stride_s: 0.25
  max_windows_per_trial: 200
  batch_size: 128
  lr: 0.001
  weight_decay: 0.0001
  epochs: 40
  patience: 6
  dropout: 0.3

ood:
  threshold: 0.9

stream:
  decision_stride_s: 0.5
  default_speed: 10

events:
  merge_gap_s: 1.0
  cooldown_s: 10.0

verifier:
  impact_search_pre_s: 1.5
  impact_search_post_s: 1.0
  post_window_s: 2.0
  pre_interval_s: [-2.0, -1.0]
  post_interval_start_s: 1.0
  still_std_g: 0.05
  combine: impact_and_any
  k: 2
  thresholds: {impact_g: 2.5, orient_deg: 45, still_std_g: 0.08, rest_s: 1.0}
  min_fall_recall: 0.95
  grid:
    impact_g: [1.8, 2.0, 2.5, 3.0, 3.5]
    orient_deg: [30, 45, 60]
    still_std_g: [0.05, 0.08, 0.12]
    rest_s: [0.5, 1.0, 1.5]
    combine: [impact_and_any, impact_and_k_of_3, all]
    k: [2]
    post_window_s: [1.5, 2.0, 3.0]

logging:
  db_path: logs/fallmon.db
  activity_log_interval_s: 2.0

notifier:
  channels: [console]      # add email, telegram when configured
  enabled_in_eval: false

evaluation:
  bootstrap_resamples: 1000
  sweep_post_window_s: [1.0, 1.5, 2.0, 3.0, 4.0]
```

Threshold defaults in `verifier.thresholds` are starting points only. The values actually used come from `models/verifier_config.json` after tuning.

---

## 18. Known risks and how to handle them

| Risk | Handling |
|---|---|
| Fall trials are short (~15 s); post window may run past trial end | `truncated` flag; report count of truncated verifications in E3 |
| D13 (lie down quickly) resembles fall posture after event | Expected hard case. Report per-code results in E6. Do not hand-tune for it. |
| Elderly ADL distribution differs from young training data, inflating OOD rate | Elderly subjects included in train split; E6 reports elderly subgroup separately |
| Some elderly subjects missing ADL codes | Loader handles missing files; summary table shows availability |
| No verifier config meets recall constraint | Report honestly, choose highest-recall config, flag in SUMMARY.md |
| Baseline DTE underperforms the paper | Report actual numbers; README notes it is a reimplementation; differences are a limitation, not hidden |

---

## 19. Definition of done

- All phases accepted.
- `pytest` passes.
- `fallmon evaluate --split test --all` regenerates every Chapter 4 table and figure from a clean clone plus the dataset.
- Dashboard demonstrates the four demo scenarios.
- README honesty statement present; no text anywhere claims physical deployment or real elderly falls.
