# E6: results by age group

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Elderly falls come from one subject (SE06); elderly subjects other than SE06 never performed D13 or D18 (see doc/dataset_notes.md).

| subgroup   | system   |   subjects |   fall_trials |   known_trials |   unknown_trials |   sensitivity |   fpr_known |   fpr_unknown |   precision |
|:-----------|:---------|-----------:|--------------:|---------------:|-----------------:|--------------:|------------:|--------------:|------------:|
| young      | baseline |          4 |           300 |            236 |               80 |        1      |      0.9619 |         1     |      0.4942 |
| young      | proposed |          4 |           300 |            236 |               80 |        0.8367 |      0.0042 |         0.05  |      0.9805 |
| elderly    | baseline |          3 |            75 |            157 |               40 |        1      |      0.9618 |         1     |      0.282  |
| elderly    | proposed |          3 |            75 |            157 |               40 |        0.6667 |      0      |         0.025 |      0.9804 |
