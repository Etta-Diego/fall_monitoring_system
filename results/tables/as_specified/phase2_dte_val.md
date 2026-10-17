# DTE validation results (development evidence, not final)

Data source: SisFall dataset replay (simulated IoT stream).

Validation split, known ADLs only. Ensemble step-level accuracy 0.7183.

| model                     |   train_windows |   val_windows |   epochs_run |   best_epoch |   val_macro_f1 |
|:--------------------------|----------------:|--------------:|-------------:|-------------:|---------------:|
| CNN 1.0 s                 |           91998 |         26464 |           21 |           15 |         0.5485 |
| CNN 2.0 s                 |           86813 |         24964 |           24 |           18 |         0.6423 |
| CNN 3.0 s                 |           81916 |         23547 |           20 |           14 |         0.7031 |
| Ensemble (decision steps) |             nan |         14249 |          nan |          nan |         0.694  |
