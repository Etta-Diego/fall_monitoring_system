# DRY RUN summary (validation split, NOT results)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream). Falls are simulated falls from SisFall, not real falls of older adults.

Split: val. Trials: Known ADLs 381, Simulated falls 300. Subjects: SA07, SA08, SA16, SA17, SE05, SE07, SE15.
OOD threshold 0.9 (both systems). Verifier: {'impact_g': 3.0, 'orient_deg': 30.0, 'still_std_g': 0.12, 'rest_s': 1.0, 'combine': 'impact_and_k_of_3', 'k': 2, 'post_window_s': 1.5, 'rearm_after_reject': True}.

## Headline (trial level, 95% bootstrap CI)

| Metric | Baseline | Proposed |
|---|---|---|
| Sensitivity | 1.000 [1.000, 1.000] | 0.960 [0.934, 0.981] |
| FPR known ADLs | 0.971 [0.953, 0.987] | 0.008 [0.000, 0.018] |
| FPR unknown ADLs | n/a | n/a |
| Precision | 0.448 [0.411, 0.484] | 0.990 [0.976, 1.000] |
| F1 | 0.619 [0.583, 0.653] | 0.975 [0.960, 0.987] |
| Specificity | 0.029 | 0.992 |
| Accuracy | 0.457 | 0.978 |
| False alerts | 496.000 | 3.000 |
| False alerts per hour | 221.050 | 1.337 |
| Decision delay median [s] | -1.230 | 1.840 |
| Decision delay p95 [s] | 0.962 | 2.853 |
| Falls first alerted > 1.5 s before impact | 0.440 | 0.000 |
| Latency mean [ms] | 1.784 | 1.836 |
| Latency p95 [ms] | 2.623 | 2.821 |

- False-alert reduction: **0.994** (496 -> 3 false alerts).
- McNemar (exact), falls: p = 0.0004883 (baseline-only correct 12, proposed-only correct 0).
- McNemar (exact), non-falls: p = 6.653e-111 (baseline-only correct 0, proposed-only correct 367).
- DTE known-ADL recognition (E1): accuracy 0.8432, macro F1 0.8191.
- Stream vs replay agreement at threshold 0.9: identical alert counts per trial; max |confidence difference| 7.75e-07 over 21748 steps.

## Secondary: calibrated threshold (reporting only, D-011)

| system            |   sensitivity |   precision |     f1 |   fpr_known |   fpr_unknown |   false_alerts_per_hour |   delay_median_s |
|:------------------|--------------:|------------:|-------:|------------:|--------------:|------------------------:|-----------------:|
| baseline @ 0.4901 |        0.8333 |       0.495 | 0.6211 |      0.6693 |           nan |                 131.026 |             0.16 |
| proposed @ 0.4901 |        0.6267 |       1     | 0.7705 |      0      |           nan |                   0     |             2    |

## Failure cases (proposed system)

**Unknown-ADL trials still alerted on (0):** none

**Known-ADL trials alerted on (3):** D14_SA08_R02, D14_SA08_R03, D14_SE07_R04

**Falls missed (12):** F01_SA08_R05, F03_SA07_R01, F06_SA07_R01, F07_SA08_R03, F08_SA17_R02, F08_SA17_R04, F08_SA17_R05, F13_SA07_R05, F13_SA08_R01, F13_SA08_R05, F15_SA07_R05, F15_SA16_R01

Baseline falls missed (0): none

## Demo cases

| Case | Trial | Rule |
|---|---|---|
| 1 | F01_SA07_R01 | genuine fall: first fall trial (by trial id) where both systems alert and the proposed alert follows a verified impact within 1 s of the reference impact |
| 2 | none | unseen fall-like ADL: first D10 trial (else any unknown ADL) where the baseline alerts and the proposed does not |
| 3 | D01_SE15_R01 | known ADL: first D01 trial (else any known ADL) where neither system opens an event |
| 4 | F01_SA08_R05 | failure case: first unknown-ADL trial the proposed system still alerts on; else first fall it misses |

E5 (post-window sweep) is reporting only and was not used for model selection.
