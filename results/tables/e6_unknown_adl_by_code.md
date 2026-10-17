# E6: false alerts per unknown ADL code

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. D10 quick sit (low chair), D11 collapse into chair, D13 lie down quickly, D18 stumble while walking.

| activity_code   | system   |   trials |   alerted_trials |    fpr |
|:----------------|:---------|---------:|-----------------:|-------:|
| D10             | baseline |       35 |               35 | 1      |
| D10             | proposed |       35 |                0 | 0      |
| D11             | baseline |       35 |               35 | 1      |
| D11             | proposed |       35 |                5 | 0.1429 |
| D13             | baseline |       25 |               25 | 1      |
| D13             | proposed |       25 |                0 | 0      |
| D18             | baseline |       25 |               25 | 1      |
| D18             | proposed |       25 |                0 | 0      |
