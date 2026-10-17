# E4 (secondary, reporting only): both systems at the validation-calibrated threshold

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Threshold 0.4901 = 95% TPR on validation known-ADL steps, fixed before the test split was opened (D-011). Computed with the decision-engine replay. Primary results use 0.9.

| system            |   sensitivity |   precision |     f1 |   fpr_known |   fpr_unknown |   false_alerts_per_hour |   delay_median_s |
|:------------------|--------------:|------------:|-------:|------------:|--------------:|------------------------:|-----------------:|
| baseline @ 0.4901 |        0.8213 |      0.4783 | 0.6045 |      0.6819 |        0.5667 |                 135.895 |             0.2  |
| proposed @ 0.4901 |        0.5147 |      1      | 0.6796 |      0      |        0      |                   0     |             1.94 |
