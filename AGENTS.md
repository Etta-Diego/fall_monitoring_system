# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, Cursor, Copilot, etc.) working in this repository.
The full specification is [fall-monitoring-PRD.md](fall-monitoring-PRD.md) (referred to below as "the PRD"). If this file and the PRD disagree, the PRD wins. Record the conflict in `doc/decisions_log.md`.

---

## 1. What this project is

An academic thesis software artefact: **"Design and Development of an Enhanced IoT-Based System for Reliable Real-Time Fall Classification and Alert Verification in Elderly Care."**

- **Baseline:** a reimplementation of Roy et al. (2023)'s Deep Time Ensemble (DTE): three small 1D-CNNs trained on **non-fall activities only**. Low max-softmax confidence means out-of-distribution (OOD), and OOD triggers an alarm directly.
- **Contribution:** a rule-based **post-event temporal verification** stage between OOD detection and the alarm:
  `OOD event -> HOLD -> examine windows around/after impact -> VERIFIED (alert) | REJECTED (unknown-activity log)`.
- **Data:** SisFall dataset replayed sample by sample as a **simulated IoT stream**. There is no hardware.
- **Research question:** how much does verification reduce false alerts (especially on unseen fall-like ADLs), and what does it cost in fall sensitivity and decision delay?

Everything except the verifier reproduces existing work as faithfully as practical, so that the baseline vs proposed comparison is fair.

---

## 2. Non-negotiable rules

### 2.1 Build discipline
1. Build **phase by phase** (PRD Section 14). At the end of each phase: run its acceptance checks, write the phase report in `doc/` (Section 5 below), then **stop and report**. Do not start the next phase until the developer says so.
2. **Phase 5 ends with a mandatory stop.** The developer must explicitly confirm before Phase 6 (test split unlocked).
3. Where the PRD says **VERIFY**, check the real dataset files or the official SisFall readme before coding. Record what you found in `doc/dataset_notes.md`. Never assume.
4. Prefer simple, readable code. An examiner may read it.
5. **No magic numbers.** Every configurable value lives in `config/default.yaml`, validated by pydantic in `src/fallmon/config.py`.

### 2.2 Data integrity and leakage (PRD Sections 7 and 11)
- Split by **participant**. A subject appears in exactly one of train / val / test.
- **Never touch the test split before Phase 6.** No threshold, hyperparameter, window size or rule may be chosen using test data.
- **Unknown ADLs (D10, D11, D13, D18) are never used for training or tuning, from any partition.** They appear only in the Phase 6 test evaluation.
- Falls are never a training class. They are OOD by design.
- The scaler is fit on **train known-ADL windows only**.
- The verifier is tuned on **validation known-ADL and fall trials only**.
- Never shuffle temporal order within a trial. Never fabricate data (no synthetic silence between chained trials; reset state at each trial boundary instead).
- `data/splits.json` is never regenerated unless `--force` is passed.
- `fallmon evaluate --split test` must refuse to run unless `results/frozen_config.yaml` exists and its SHA-256 matches the current config + models.
- Do not weaken, skip or delete a guard or its test to make something pass. If a guard fails, stop and report.

### 2.3 Honesty rules (PRD Section 2.3)
- Describe the data source as **"SisFall dataset replay (simulated IoT stream)"** in all UI, logs, README and notifications.
- Every notification subject/prefix includes **`[SIMULATED]`**.
- Never call SisFall falls "elderly falls". Use **"simulated falls from SisFall"**.
- Never write text implying physical hardware, a real wearable, or real elderly falls.
- Report results exactly as computed, including failures. No cherry-picking. If no verifier configuration meets the recall constraint, say so; do not silently relax it.
- If the baseline underperforms the paper, report the real numbers and note it as a reimplementation limitation.

### 2.4 Out of scope (do not build)
Hardware/firmware (ESP32, Raspberry Pi, BLE, MQTT), XAI (SHAP/LIME), a fall class in the classifier, deep-learning verifiers or transformers, any "better classifier" replacing the pipeline, user accounts/auth/cloud, retraining from feedback.

---

## 3. Tech stack and layout

Python 3.11, PyTorch (CPU), scikit-learn, scipy, numpy, pandas, statsmodels (McNemar), PyYAML + pydantic, Typer (CLI), SQLite (stdlib), Streamlit + Plotly (dashboard), matplotlib (300 dpi PNG thesis figures), pytest.

Set seeds (Python, numpy, torch) from config. Use `torch.use_deterministic_algorithms(True)` where it does not break ops.

Layout (PRD Section 4):
```
config/default.yaml          all tunables
data/raw/SisFall_dataset/    dataset (gitignored)
data/processed/              caches (gitignored)
data/splits.json             committed once generated
models/                      weights (committed, D-015), scaler.json, dte_meta.json, verifier_config.json
results/tables, figures/     Chapter 4 outputs; frozen_config.yaml + .sha256
logs/fallmon.db              SQLite
src/fallmon/                 package (config, data_loader, preprocessing, splits, windowing,
                             dte, train, ood, events, verifier, tune_verifier, pipeline,
                             stream_simulator, storage, notifier, evaluation, guards, cli)
app/dashboard.py             Streamlit
tests/                       pytest, including leakage guards
doc/                         thesis documentation for Chapters 4 and 5 (see Section 5)
notebooks/                   exploration only; never imported by src
```

## 4. Commands

```
pip install -r requirements.txt
pytest                                   # must pass before any phase is reported done
fallmon prepare-data                     # index, convert, split
fallmon train                            # DTE models + scaler
fallmon tune-verifier                    # grid search, validation only
fallmon stream --trial ID --mode baseline|proposed|both --speed N
fallmon batch --split val --mode both
fallmon freeze                           # lock config + models (end of Phase 5)
fallmon evaluate --split test --all      # Phase 6 only
fallmon demo --case N --speed N
streamlit run app/dashboard.py
```

---

## 5. Thesis documentation in `doc/` (required, ongoing)

The developer is a student who will write **Chapter 4 (implementation, testing and results)** and **Chapter 5 (discussion, conclusion and recommendations)** of the thesis from this repository. `doc/` is where you leave them the material to do that. Writing it is part of the job, not an afterthought.

**Write to `doc/` at these moments, without being asked:**

| Trigger | Where |
|---|---|
| A VERIFY item is checked against the dataset/readme | `doc/dataset_notes.md` |
| A design decision is made, a PRD default is changed, or the implementation deviates from the PRD or from Roy et al. | `doc/decisions_log.md` (new numbered entry) |
| A phase's acceptance checks finish | `doc/phase_reports/phaseN_<name>.md` from the template |
| An experiment, training run, tuning run or evaluation produces numbers | `doc/experiments_log.md` (numbers + source file path + config/hash) |
| A limitation, threat to validity, surprising result or failure case is found | `doc/limitations.md` |
| A figure or table is generated that belongs in the thesis | Add it to the artefact map in `doc/chapter4_guide.md` |
| Something suggests future work or a recommendation | `doc/chapter5_guide.md` |

**How to write it:**
- Audience: the student writing the thesis, then their supervisor and examiner. Plain, precise English. Explain *why*, not just *what*.
- Copy numbers exactly from the generated files and cite the file path (e.g. `results/tables/e4_end_to_end.csv`). Never round differently from the source or invent a number.
- Say which split the numbers came from (train / val / test). Validation numbers are never presented as final results.
- Keep the honesty rules (Section 2.3) in the docs too.
- Append and update; do not rewrite history. If an earlier entry turns out wrong, add a correction that points to it.
- Keep entries short. Bullet points and small tables are fine; the student turns them into prose.
