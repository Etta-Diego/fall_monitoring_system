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
