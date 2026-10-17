# E5: post-window sensitivity (REPORTING ONLY, not used for model selection)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Proposed system with every other parameter frozen; only post_window_s varies. Post interval starts 1 s after the impact, so at post_window_s = 1 s it is empty and only the impact rule can pass.

|   post_window_s |   sensitivity |   fpr_known |   fpr_unknown |   delay_median_s |   delay_p95_s | selected   |
|----------------:|--------------:|------------:|--------------:|-----------------:|--------------:|:-----------|
|             1   |        0      |      0      |           nan |           nan    |       nan     | False      |
|             1.5 |        0.96   |      0.0079 |           nan |             1.84 |         2.853 | True       |
|             2   |        0.9633 |      0.063  |           nan |             2.32 |         2.88  | False      |
|             3   |        0.8367 |      0.084  |           nan |             3.32 |         3.79  | False      |
|             4   |        0.64   |      0.0709 |           nan |             4.26 |         4.714 | False      |
