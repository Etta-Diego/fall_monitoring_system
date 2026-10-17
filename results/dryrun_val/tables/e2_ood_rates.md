# E2: share of decision steps flagged OOD

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Primary threshold 0.9; calibrated threshold 0.4901 (95% TPR on validation known ADLs, D-011).

| comparison                          | level   |   Known ADLs |   Simulated falls |
|:------------------------------------|:--------|-------------:|------------------:|
| step OOD rate at threshold 0.9      | step    |       0.3649 |            0.4729 |
| step OOD rate at threshold 0.490061 | step    |       0.05   |            0.0785 |
