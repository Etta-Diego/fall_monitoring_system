# E5: post-window sensitivity (REPORTING ONLY, not used for model selection)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Proposed system with every other parameter frozen; only post_window_s varies. Post interval starts 1 s after the impact, so at post_window_s = 1 s it is empty: the orientation, stillness and rest rules cannot pass, so a combination needing them verifies nothing.

|   post_window_s |   sensitivity |   fpr_known |   fpr_unknown |   delay_median_s |   delay_p95_s | selected   |
|----------------:|--------------:|------------:|--------------:|-----------------:|--------------:|:-----------|
|             1   |        0      |      0      |        0      |           nan    |       nan     | False      |
|             1.5 |        0.8027 |      0.0025 |        0.0417 |             1.88 |         2.88  | True       |
|             2   |        0.8027 |      0.0865 |        0.125  |             2.38 |         3.22  | False      |
|             3   |        0.6267 |      0.1043 |        0.0917 |             3.28 |         3.786 | False      |
|             4   |        0.5413 |      0.084  |        0.05   |             4.28 |         4.538 | False      |
