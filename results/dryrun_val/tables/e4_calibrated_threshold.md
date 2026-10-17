# E4 (secondary, reporting only): both systems at the validation-calibrated threshold

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Threshold 0.4901 = 95% TPR on validation known-ADL steps, fixed before the test split was opened (D-011). Computed with the decision-engine replay. Primary results use 0.9.

| system            |   sensitivity |   precision |     f1 |   fpr_known |   fpr_unknown |   false_alerts_per_hour |   delay_median_s |
|:------------------|--------------:|------------:|-------:|------------:|--------------:|------------------------:|-----------------:|
| baseline @ 0.4901 |        0.8333 |       0.495 | 0.6211 |      0.6693 |           nan |                 131.026 |             0.16 |
| proposed @ 0.4901 |        0.6267 |       1     | 0.7705 |      0      |           nan |                   0     |             2    |
