# Decisions log

One numbered entry per design decision, PRD default change, or deviation from the PRD or from Roy et al. (2023). Append only. To correct an entry, add a new one that references it.

Entry format:

```
## D-NNN: <short title>
- Date / phase:
- Context: what needed deciding
- Decision:
- Alternatives considered:
- Reason:
- Effect on results / fairness of comparison:
- Evidence: file paths, PRD section
```

---

## D-001: Activity grouping into known ADLs, unknown ADLs and falls
- Date / phase: 2026-10-16 / pre-build (from PRD 5.3)
- Context: the proposed system has to be tested on fall-like activities that no trained or tuned component has seen.
- Decision: known ADLs = D01–D09, D12, D14–D17, D19; unknown ADLs = D10, D11, D13, D18; falls = F01–F15.
- Alternatives considered: holding out no ADLs (cannot test the false-alarm-on-unfamiliar-activity gap).
- Reason: unknown ADLs are fall-like and are never used for training or tuning. D08, D12, D14 and D19 stay known so the verifier can be tuned against abrupt but known movements.
- Effect: unknown-ADL false-alert rate measures generalisation to activities neither system has seen.
- Evidence: PRD 5.3, 7.2.

## D-002: Same OOD threshold (0.9) for baseline and proposed
- Date / phase: 2026-10-16 / pre-build (from PRD 8.4)
- Decision: both modes use `ood.threshold = 0.9`, the value cited in thesis Section 2.1.8.
- Reason: the only difference between modes is the verifier, so any change in false alerts can be attributed to it.
- Evidence: PRD 8.4.

## D-003: Causal filter for both training and streaming
- Date / phase: 2026-10-16 / pre-build (from PRD 6.1)
- Decision: default `preprocessing.offline_zero_phase: false`; `filtfilt` kept as an option.
- Reason: zero train/serve skew. The effect of the alternative is checked and reported in Phase 4.
- Evidence: PRD 6, 6.1.

## D-004: Python 3.10 instead of 3.11
- Date / phase: 2026-10-16 / Phase 1 setup
- Context: the PRD (Section 3) specifies Python 3.11; the development machine has Python 3.10.12 only.
- Decision: use Python 3.10 (`requires-python >= 3.10`). Developer's choice.
- Alternatives considered: installing 3.11 via `uv` or the deadsnakes PPA.
- Reason: no 3.11-only language features are needed; all dependencies support 3.10.
- Effect on results / fairness: none. Both baseline and proposed run in the same environment.
- Evidence: `python3 --version` -> 3.10.12; `pyproject.toml`.

## D-005: Subject ID taken from the folder, not the file name
- Date / phase: 2026-10-16 / Phase 1
- Context: `SA15/` contains five files named `D17_SE15_R01..05.txt`. They differ from the files of the same name in `SE15/`, and SA15 otherwise has no D17. They are SA15's recordings with a wrong subject ID in the name (see `dataset_notes.md`).
- Decision: `data_loader` assigns `subject_id` from the parent folder. Any folder/file-name mismatch is logged as a warning and listed in the dataset summary.
- Alternatives considered: trusting the file name (would put SA15's data under SE15, so an elderly subject would get young-subject data and SE15 would have 10 D17 trials); dropping the 5 files.
- Reason: keeps participant-level splitting correct (no young data leaking into an elderly subject's partition) and loses no data.
- Effect: SA15 gets its 5 D17 trials; SE15 keeps its own 5.
- Evidence: checksums of `SA15/D17_SE15_R0*.txt` vs `SE15/D17_SE15_R0*.txt` all differ.

## D-006: Dataset copy obtained from the GitHub mirror
- Date / phase: 2026-10-16 / Phase 1
- Context: the original SISTEMIC/UDEA site is unreliable.
- Decision: use `Fall-Prevention-Team/sisfallData` (commit `8352a0f`), cross-checked against the Hugging Face mirror. Cite the MDPI paper (Sucerquia et al., 2017) in the thesis.
- Effect: 4,505 files instead of the 4,510 stated in the readme; both mirrors agree, so this reflects the original distribution.
- Evidence: `dataset_notes.md`.

## D-007: Baseline DTE is a reimplementation from the paper
- Date / phase: 2026-10-16 / Phase 2
- Context: PRD 8 asks to adapt the official code of Roy et al. (2023) if any exists.
- Finding: no official code found. Searched the web for the paper title and authors (Roy, Komini, Girdzijauskas, *AI Communications* 36(4), 2023, DOI 10.3233/AIC-220205). The group's related Zenodo record 8079816 ("Out of distribution in Human Activity Recognition", SAIS 2022) contains only the PDF.
- Decision: implement the DTE as specified in PRD 8 (three 1D-CNNs on 1, 2 and 3 s windows, mean softmax, max-softmax confidence, threshold 0.9) and state in the README and thesis that it is a reimplementation from the paper's description.
- Effect: architecture and training details may differ from the original; any gap with the paper's reported numbers is a limitation, not hidden.

## D-008: Training stride 0.24 s instead of 0.25 s
- Date / phase: 2026-10-16 / Phase 2
- Context: PRD default `dte.train_stride_s: 0.25` is 12.5 samples at 50 Hz, which cannot be used as a window step.
- Decision: 0.24 s (12 samples). The config validator now rejects any stride or window length that is not a whole number of samples.
- Alternatives: 0.26 s (13 samples); rounding silently in code (rejected: hides the real value used).
- Effect: ~4% more training windows than 0.25 s would give. Training stride only; it does not affect decision stride (0.5 s = 25 samples) or anything at run time.

## D-009: Coarse activity groups plus a shared "static" class for DTE training labels
- Date / phase: 2026-10-17 / Phase 2. Chosen by the developer (option A) after the as-specified run X-002.
- Context: with one label per activity code (PRD 8.1), windows where the person is simply standing or sitting still carry six different labels (D07, D08, D09, D15, D16, D17...). The DTE cannot be confident on them, so 99.2% of validation known-ADL trials had a step below the 0.9 threshold, and the trial-level AUROC for falls was 0.380 (X-002, `phase_reports/phase2_baseline_dte.md`). The baseline would alarm on almost every normal activity, making the comparison with the proposed system meaningless.
- Decision (`dte.label_scheme: grouped_static`):
  1. Known-ADL codes are merged into 8 coarse groups (`activities.class_groups`): walking (D01, D02), jogging (D03, D04), stairs (D05, D06), sit_stand (D07, D08, D09), lying (D12, D14), bending (D15, D16), car (D17), jump (D19).
  2. Any training window where the person is still for the whole window, meaning std(Am) < 0.02 g **and** mean(Gm) < 10 °/s (`dte.static`), is labelled `static`, whatever its activity.
  So 9 classes in total. The confidence rule, threshold 0.9, architecture and training procedure are unchanged.
- How the thresholds were chosen: from **train-split** known-ADL 1 s windows only. With these values no walking/jogging window is static, and 41–61% of sit/lie/bend/car/jump windows are, which is what "standing or sitting still" should look like. Not tuned against any OOD or fall outcome.
- Alternatives considered: (B) keep per-code labels and report a near-100% baseline false-alarm rate; (C) lower the threshold (would need 0.265 for 95% TPR on val; rejected, 0.9 is cited in the thesis and fixed for fairness, D-002).
- Effect on fairness: the same DTE serves both baseline and proposed modes, so the comparison is still "same detector, with vs without verification". Falls and unknown ADLs remain unseen in training (guard 2 checks activity codes, unaffected by relabelling).
- Deviation from Roy et al.: their per-activity labelling is replaced. This must be stated in Chapter 4.5 and the limitations. The as-specified variant stays reproducible with `label_scheme: activity`; its models and tables are archived in `models/as_specified/` and `results/*/as_specified/`.
- Evidence: X-002 (as specified), X-003 (this scheme).

## D-010: Phase 3 implementation details not fixed by the PRD
- Date / phase: 2026-10-17 / Phase 3
- Decisions:
  1. **Extra decision status `COOLDOWN`** for an OOD step that cannot open an event because an alert was raised less than `cooldown_s` ago. PRD 12.2 lists only KNOWN/HOLD/ALERT/REJECTED; without this, such steps would be mislabelled.
  2. **`new_alert` flag** on the decision record, true only on the step where an alert is emitted. Steps that merely belong to an alerted event carry status ALERT, so counting statuses would over-count alerts.
  3. **`t_close_s` column** added to `events` (PRD 12.3 schema), so event duration is recorded.
  4. **Latency** = time from receiving the raw sample that completes a decision step to the decision being produced (inference + event logic). Database and notification I/O are excluded, since they are not part of the decision.
  5. **Activity log** is flushed when an event opens, so activity before an event is not logged with a timestamp after it.
  6. **Interim test lock:** `stream` and `batch` refuse test-split subjects until the frozen-config unlock exists (Phase 5).
  7. **Decision time** of a step = end of its window at 50 Hz (n / 50 s), the same convention as offline evaluation.
- Effect: none on results. Item 4 defines what E7 measures.

## D-011: Secondary baseline at the validation-calibrated threshold (reporting only)
- Date / phase: 2026-10-17 / after Phase 3. Approved by the developer.
- Context: at the fixed threshold 0.9 the baseline alerts on ~97% of validation known-ADL trials (X-003, X-004). An examiner may ask whether the false-alert reduction would survive a better-tuned baseline.
- Decision: Phase 6 also reports the baseline (and, for the same threshold, the proposed system) at the threshold giving 95% TPR on **validation** known-ADL steps: 0.4901, stored in `models/dte_meta.json` (`val_metrics.ood.threshold_at_95tpr_val_known`). Config switch `evaluation.report_calibrated_baseline: true`.
- Primary results stay at 0.9 (D-002). The calibrated threshold comes from validation data only and is fixed before the test split is unlocked.
- Effect: adds rows to E2/E4; no change to models or tuning.

## D-012: Re-arm after a rejected verification (proposed mode)
- Date / phase: 2026-10-17 / Phase 4
- Context: Phase 3 showed that in 44% of val fall trials the first OOD event opens more than 1.5 s before the impact (X-004). In PRD 9.2 the verifier runs once per event, searching for the impact in [t_open − 1.5 s, t_open + 1.0 s]. If an early event stays open (merging OOD steps) through the real impact, the real impact is never examined.
- Decision: config option `verifier.rearm_after_reject`. When true, a REJECTED verification ends its event at the decision time, so the next OOD step opens a fresh event with its own impact search and verification. Accepted alerts are unchanged (cooldown as before). Whether to use it was **left to the tuning objective**: it was added to the validation grid as `[false, true]`, with ties broken in favour of `false` (the PRD behaviour).
- Result (validation grid, X-005): with `false`, no configuration reaches the fall-recall constraint (best recall 0.65); with `true`, 357 of 1,215 configurations do. Selected: `true`.
- Supporting design choice: while a verification is pending, no new event can open (`EventTracker.blocked`); OOD steps in that period are reported with status HOLD. One verification at a time per stream.
- Effect on fairness: proposed mode only; the baseline is unchanged. More verifications per trial (2,458 on 681 val trials), each one a fresh chance of a false alert, so the re-arm cannot hide false alerts; it can only add them.
- Evidence: `tests/test_pipeline.py::test_rearm_after_reject_catches_fall_inside_early_event`, `results/tables/verifier_grid_val.csv`.

## D-013: Verifier feature windows made configurable
- Date / phase: 2026-10-17 / Phase 4
- Decision: the ±0.5 s impact-peak window and the 0.5 s rolling-std window of PRD 9.3 are config values (`verifier.impact_window_s: 1.0`, `verifier.rolling_std_s: 0.5`) instead of constants in code (no magic numbers, PRD 0.5). Values unchanged.
- Note on the rest rule: the post interval runs from t_impact + 1.0 s to t_impact + post_window_s, so with post_window_s = 1.5 s it is only 0.5 s long and `low_activity_s` cannot reach rest_s ≥ 1.0 s. This is a property of the PRD's parameterisation, not a bug. It is reported with the selected configuration rather than changed (changing it now would be redesign after seeing validation results).
- Rules evaluate to false when their feature has no data (e.g. trial ended before the post interval); such verifications are flagged `truncated`.

## D-014: Console-only notifications (email and Telegram removed from scope)
- Date / phase: 2026-10-17 / Phase 5. Developer's decision.
- Decision: the system notifies through the console only; every alert is also stored in the SQLite alert log and shown on the dashboard. Email (SMTP) and Telegram notifiers are not built. All references were removed from the PRD (Sections 2.1, 3, 4, 12.4, 14 Phase 5, 17), `config/default.yaml`, `src/fallmon/config.py`, `src/fallmon/notifier.py` and `AGENTS.md`; `.env.example` and the `python-dotenv` dependency were deleted (they existed only for those channels).
- Effect: no effect on any result. The Phase 5 acceptance item "email or Telegram test message" no longer applies. `notifier.channels` accepts only `console`.
