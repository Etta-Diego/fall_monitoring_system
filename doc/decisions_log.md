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
