# Selected verifier configuration (validation split, development evidence)

Data source: SisFall dataset replay (simulated IoT stream).

357 of 2430 configurations meet fall recall >= 0.95; selected the lowest known-ADL false-alert rate (ties: shorter post window, simpler combine, no re-arm, higher recall, grid order). Grid of 2430 configurations; full results in verifier_grid_val.csv.

| setting                                               | value             |
|:------------------------------------------------------|:------------------|
| impact_g                                              | 3.0               |
| orient_deg                                            | 30.0              |
| still_std_g                                           | 0.12              |
| rest_s                                                | 1.0               |
| combine                                               | impact_and_k_of_3 |
| k                                                     | 2                 |
| post_window_s                                         | 1.5               |
| rearm_after_reject                                    | True              |
| val proposed: fa_rate_known                           | 0.0079            |
| val proposed: fall_recall                             | 0.96              |
| val proposed: known_alerts                            | 3                 |
| val proposed: fall_alerts                             | 288               |
| val proposed: verifications                           | 2458              |
| val proposed: truncated                               | 139               |
| val proposed: median_first_alert_minus_impact_s       | 1.84              |
| val proposed: p95_first_alert_minus_impact_s          | 2.853             |
| val proposed: falls_first_alert_before_impact_gt_1_5s | 0.0               |
| val baseline: fa_rate_known                           | 0.9711            |
| val baseline: fall_recall                             | 1.0               |
| val baseline: known_alerts                            | 496               |
| val baseline: fall_alerts                             | 320               |
| val baseline: verifications                           | 0                 |
| val baseline: truncated                               | 0                 |
| val baseline: median_first_alert_minus_impact_s       | -1.23             |
| val baseline: p95_first_alert_minus_impact_s          | 0.962             |
| val baseline: falls_first_alert_before_impact_gt_1_5s | 0.44              |
