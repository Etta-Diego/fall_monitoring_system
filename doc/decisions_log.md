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
