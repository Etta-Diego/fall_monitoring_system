# E2: OOD detection by DTE confidence (threshold-free)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). AUROC/AUPRC with OOD (falls and/or unknown ADLs) as the positive class; score = 1 − confidence. Trial level uses each trial's minimum confidence.

| comparison                    | level                  |   n_known |   n_ood |   auroc |   auprc |
|:------------------------------|:-----------------------|----------:|--------:|--------:|--------:|
| known vs falls                | step                   |     14249 |    7499 |  0.6556 |  0.4358 |
| known vs falls                | trial (min confidence) |       381 |     300 |  0.62   |  0.5112 |
| known vs falls + unknown ADLs | step                   |     14249 |    7499 |  0.6556 |  0.4358 |
| known vs falls + unknown ADLs | trial (min confidence) |       381 |     300 |  0.62   |  0.5112 |
