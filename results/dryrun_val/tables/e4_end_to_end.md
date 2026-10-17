# E4: end-to-end comparison, baseline vs proposed (same trials)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Threshold 0.9. Trial-level: a trial is alerted if at least one ALERT was emitted. 95% bootstrap CIs in brackets (1000 resamples over trials, seed 42). Decision delay = first alert − reference impact (argmax Am), fall trials; negative = before impact. Baseline: TP 300, FN 0, FP 370, TN 11. Proposed: TP 288, FN 12, FP 3, TN 378. McNemar contingency: falls {'n_trials': 300, 'both_correct': 288, 'baseline_only_correct': 12, 'proposed_only_correct': 0, 'both_wrong': 0, 'p_value': 0.00048828125}, non-falls {'n_trials': 381, 'both_correct': 11, 'baseline_only_correct': 0, 'proposed_only_correct': 367, 'both_wrong': 3, 'p_value': 6.653062250012736e-111}.

| metric                                       | baseline             | proposed             |
|:---------------------------------------------|:---------------------|:---------------------|
| Sensitivity (recall)                         | 1.000 [1.000, 1.000] | 0.960 [0.934, 0.981] |
| Specificity                                  | 0.029                | 0.992                |
| Precision                                    | 0.448 [0.411, 0.484] | 0.990 [0.976, 1.000] |
| F1                                           | 0.619 [0.583, 0.653] | 0.975 [0.960, 0.987] |
| Accuracy                                     | 0.457                | 0.978                |
| FPR known ADLs                               | 0.971 [0.953, 0.987] | 0.008 [0.000, 0.018] |
| FPR unknown ADLs                             | n/a                  | n/a                  |
| False alerts (count)                         | 496.000              | 3.000                |
| False alerts per hour                        | 221.050              | 1.337                |
| Decision delay mean [s]                      | -1.435               | 1.923                |
| Decision delay median [s]                    | -1.230               | 1.840                |
| Decision delay p95 [s]                       | 0.962                | 2.853                |
| Falls first alerted > 1.5 s before impact    | 0.440                | 0.000                |
| Processing latency mean [ms]                 | 1.784                | 1.836                |
| Processing latency p95 [ms]                  | 2.623                | 2.821                |
| False-alert reduction (proposed vs baseline) |                      | 0.994                |
| McNemar p, falls (exact)                     |                      | 0.0004883            |
| McNemar p, non-falls (exact)                 |                      | 6.653e-111           |
