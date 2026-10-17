# DTE validation results (development evidence, not final)

Data source: SisFall dataset replay (simulated IoT stream).

Validation split, known ADLs only. Label scheme: grouped_static. Ensemble step-level accuracy 0.8432.

| model                     |   train_windows |   val_windows |   epochs_run |   best_epoch |   val_macro_f1 |
|:--------------------------|----------------:|--------------:|-------------:|-------------:|---------------:|
| CNN 1.0 s                 |           91998 |         26464 |           24 |           18 |         0.8025 |
| CNN 2.0 s                 |           86813 |         24964 |           18 |           12 |         0.8457 |
| CNN 3.0 s                 |           81916 |         23547 |           17 |           11 |         0.8786 |
| Ensemble (decision steps) |             nan |         14249 |          nan |          nan |         0.8191 |
