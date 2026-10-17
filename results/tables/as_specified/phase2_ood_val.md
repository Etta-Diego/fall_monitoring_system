# OOD sanity check on validation (development evidence, not final)

Data source: SisFall dataset replay (simulated IoT stream).

Step-level and trial-level (any OOD step, no event logic) rates at the fixed threshold. threshold_at_95tpr is a sensitivity note only and is not used for decisions (PRD 8.4).

| metric                                 |   value |
|:---------------------------------------|--------:|
| threshold                              |  0.9    |
| val_known_step_ood_rate                |  0.5756 |
| val_fall_step_ood_rate                 |  0.72   |
| val_known_trials_with_any_ood_step     |  0.9921 |
| val_fall_trials_with_any_ood_step      |  1      |
| val_auroc_known_vs_fall_step           |  0.559  |
| val_auroc_known_vs_fall_trial_min_conf |  0.3798 |
| threshold_at_95tpr_val_known           |  0.2654 |
| median_conf_val_known                  |  0.8272 |
| median_conf_val_fall                   |  0.7002 |
