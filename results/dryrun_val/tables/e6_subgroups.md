# E6: results by age group

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Elderly falls come from one subject (SE06); elderly subjects other than SE06 never performed D13 or D18 (see doc/dataset_notes.md).

| subgroup   | system   |   subjects |   fall_trials |   known_trials |   unknown_trials |   sensitivity |   fpr_known |   fpr_unknown |   precision |
|:-----------|:---------|-----------:|--------------:|---------------:|-----------------:|--------------:|------------:|--------------:|------------:|
| young      | baseline |          4 |           300 |            235 |                0 |          1    |      0.966  |           nan |      0.5693 |
| young      | proposed |          4 |           300 |            235 |                0 |          0.96 |      0.0085 |           nan |      0.9931 |
| elderly    | baseline |          3 |             0 |            146 |                0 |        nan    |      0.9795 |           nan |      0      |
| elderly    | proposed |          3 |             0 |            146 |                0 |        nan    |      0.0068 |           nan |      0      |
