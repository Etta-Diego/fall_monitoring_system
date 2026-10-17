# E2: share of decision steps flagged OOD

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Primary threshold 0.9; calibrated threshold 0.4901 (95% TPR on validation known ADLs, D-011).

| comparison                          | level   |   Known ADLs |   Unknown ADLs |   Simulated falls |
|:------------------------------------|:--------|-------------:|---------------:|------------------:|
| step OOD rate at threshold 0.9      | step    |       0.312  |         0.4535 |            0.4473 |
| step OOD rate at threshold 0.490061 | step    |       0.0481 |         0.0579 |            0.0731 |
