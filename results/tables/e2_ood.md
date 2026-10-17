# E2: OOD detection by DTE confidence (threshold-free)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. AUROC/AUPRC with OOD (falls and/or unknown ADLs) as the positive class; score = 1 − confidence. Trial level uses each trial's minimum confidence.

| comparison                    | level                  |   n_known |   n_ood |   auroc |   auprc |
|:------------------------------|:-----------------------|----------:|--------:|--------:|--------:|
| known vs falls                | step                   |     14861 |    9375 |  0.6837 |  0.5011 |
| known vs falls                | trial (min confidence) |       393 |     375 |  0.644  |  0.5924 |
| known vs unknown ADLs         | step                   |     14861 |    2280 |  0.6344 |  0.1736 |
| known vs unknown ADLs         | trial (min confidence) |       393 |     120 |  0.4204 |  0.2029 |
| known vs falls + unknown ADLs | step                   |     14861 |   11655 |  0.6741 |  0.5475 |
| known vs falls + unknown ADLs | trial (min confidence) |       393 |     495 |  0.5898 |  0.6213 |
