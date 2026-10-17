# Final evaluation summary

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream). Falls are simulated falls from SisFall, not real falls of older adults.

Split: test. Trials: Known ADLs 393, Unknown ADLs 120, Simulated falls 375. Subjects: SA11, SA18, SA19, SA23, SE06, SE11, SE14.
OOD threshold 0.9 (both systems). Verifier: {'impact_g': 3.0, 'orient_deg': 30.0, 'still_std_g': 0.12, 'rest_s': 1.0, 'combine': 'impact_and_k_of_3', 'k': 2, 'post_window_s': 1.5, 'rearm_after_reject': True}.

## Headline (trial level, 95% bootstrap CI)

| Metric | Baseline | Proposed |
|---|---|---|
| Sensitivity | 1.000 [1.000, 1.000] | 0.803 [0.760, 0.842] |
| FPR known ADLs | 0.962 [0.942, 0.980] | 0.003 [0.000, 0.008] |
| FPR unknown ADLs | 1.000 [1.000, 1.000] | 0.042 [0.009, 0.083] |
| Precision | 0.430 [0.398, 0.461] | 0.980 [0.963, 0.994] |
| F1 | 0.601 [0.569, 0.631] | 0.883 [0.854, 0.909] |
| Specificity | 0.029 | 0.988 |
| Accuracy | 0.439 | 0.910 |
| False alerts | 618 | 6 |
| False alerts per hour | 225.761 | 2.192 |
| Decision delay median [s] | -1.400 | 1.880 |
| Decision delay p95 [s] | 0.466 | 2.880 |
| Falls first alerted > 1.5 s before impact | 0.445 | 0.000 |
| Latency mean [ms] | 1.660 | 1.841 |
| Latency p95 [ms] | 2.206 | 2.816 |

- False-alert reduction: **0.990** (618 -> 6 false alerts).
- McNemar (exact), falls: p = 1.059e-22 (baseline-only correct 74, proposed-only correct 0).
- McNemar (exact), non-falls: p = 1.564e-148 (baseline-only correct 0, proposed-only correct 492).
- DTE known-ADL recognition (E1): accuracy 0.8739, macro F1 0.8412.
- Stream vs replay agreement at threshold 0.9: identical alert counts per trial; max |confidence difference| 5.96e-07 over 26516 steps.

## Secondary: calibrated threshold (reporting only, D-011)

| system            |   sensitivity |   precision |     f1 |   fpr_known |   fpr_unknown |   false_alerts_per_hour |   delay_median_s |
|:------------------|--------------:|------------:|-------:|------------:|--------------:|------------------------:|-----------------:|
| baseline @ 0.4901 |        0.8213 |      0.4783 | 0.6045 |      0.6819 |        0.5667 |                 135.895 |             0.2  |
| proposed @ 0.4901 |        0.5147 |      1      | 0.6796 |      0      |        0      |                   0     |             1.94 |

## Failure cases (proposed system)

**Unknown-ADL trials still alerted on (5):** D11_SA18_R01, D11_SA18_R03, D11_SA18_R04, D11_SA18_R05, D11_SE11_R01

**Known-ADL trials alerted on (1):** D14_SA11_R05

**Falls missed (74):** F01_SA23_R03, F01_SA23_R04, F01_SE06_R04, F02_SE06_R04, F03_SA23_R02, F03_SA23_R03, F03_SA23_R04, F03_SE06_R05, F05_SA23_R01, F05_SA23_R02, F06_SE06_R02, F06_SE06_R04, F07_SA19_R01, F07_SA19_R03, F07_SA23_R03, F07_SA23_R04, F07_SE06_R02, F07_SE06_R03, F07_SE06_R04, F07_SE06_R05, F08_SA23_R02, F08_SA23_R03, F08_SA23_R04, F08_SA23_R05, F08_SE06_R01, F08_SE06_R03, F08_SE06_R04, F08_SE06_R05, F09_SA23_R01, F09_SA23_R03, F09_SA23_R04, F09_SE06_R03, F09_SE06_R04, F10_SA11_R03, F10_SA18_R01, F10_SA19_R01, F10_SA19_R02, F10_SA19_R04, F10_SA23_R01, F10_SA23_R04, F10_SA23_R05, F10_SE06_R01, F10_SE06_R02, F10_SE06_R03, F10_SE06_R04, F10_SE06_R05, F11_SA23_R03, F11_SA23_R04, F12_SA23_R04, F12_SE06_R05, F13_SA18_R03, F13_SA18_R04, F13_SA19_R01, F13_SA19_R03, F13_SA23_R02, F13_SA23_R03, F13_SA23_R04, F13_SE06_R01, F13_SE06_R02, F13_SE06_R04, F13_SE06_R05, F14_SA11_R03, F14_SA11_R04, F14_SA23_R01, F14_SA23_R02, F14_SA23_R03, F14_SA23_R04, F14_SA23_R05, F15_SA18_R03, F15_SA23_R01, F15_SA23_R02, F15_SA23_R03, F15_SA23_R04, F15_SA23_R05

Baseline falls missed (0): none

## Demo cases

| Case | Trial | Rule |
|---|---|---|
| 1 | F01_SA11_R01 | genuine fall: first fall trial (by trial id) where both systems alert and the proposed alert follows a verified impact within 1 s of the reference impact |
| 2 | D10_SA11_R01 | unseen fall-like ADL: first D10 trial (else any unknown ADL) where the baseline alerts and the proposed does not |
| 3 | D01_SA19_R01 | known ADL: first D01 trial (else any known ADL) where neither system opens an event |
| 4 | D11_SA18_R01 | failure case: first unknown-ADL trial the proposed system still alerts on; else first fall it misses |

E5 (post-window sweep) is reporting only and was not used for model selection.
