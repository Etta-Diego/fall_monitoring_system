# E4: end-to-end comparison, baseline vs proposed (same trials)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Threshold 0.9. Trial-level: a trial is alerted if at least one ALERT was emitted. 95% bootstrap CIs in brackets (1000 resamples over trials, seed 42). Decision delay = first alert − reference impact (argmax Am), fall trials; negative = before impact. Baseline: TP 375, FN 0, FP 498, TN 15. Proposed: TP 301, FN 74, FP 6, TN 507. McNemar contingency: falls {'n_trials': 375, 'both_correct': 301, 'baseline_only_correct': 74, 'proposed_only_correct': 0, 'both_wrong': 0, 'p_value': 1.0587911840678754e-22}, non-falls {'n_trials': 513, 'both_correct': 15, 'baseline_only_correct': 0, 'proposed_only_correct': 492, 'both_wrong': 6, 'p_value': 1.5641274181117976e-148}.

| metric                                       | baseline             | proposed             |
|:---------------------------------------------|:---------------------|:---------------------|
| Sensitivity (recall)                         | 1.000 [1.000, 1.000] | 0.803 [0.760, 0.842] |
| Specificity                                  | 0.029                | 0.988                |
| Precision                                    | 0.430 [0.398, 0.461] | 0.980 [0.963, 0.994] |
| F1                                           | 0.601 [0.569, 0.631] | 0.883 [0.854, 0.909] |
| Accuracy                                     | 0.439                | 0.910                |
| FPR known ADLs                               | 0.962 [0.942, 0.980] | 0.003 [0.000, 0.008] |
| FPR unknown ADLs                             | 1.000 [1.000, 1.000] | 0.042 [0.009, 0.083] |
| False alerts (count)                         | 618                  | 6                    |
| False alerts per hour                        | 225.761              | 2.192                |
| Decision delay mean [s]                      | -1.619               | 1.981                |
| Decision delay median [s]                    | -1.400               | 1.880                |
| Decision delay p95 [s]                       | 0.466                | 2.880                |
| Falls first alerted > 1.5 s before impact    | 0.445                | 0.000                |
| Processing latency mean [ms]                 | 1.660                | 1.841                |
| Processing latency p95 [ms]                  | 2.206                | 2.816                |
| False-alert reduction (proposed vs baseline) |                      | 0.990                |
| McNemar p, falls (exact)                     |                      | 1.059e-22            |
| McNemar p, non-falls (exact)                 |                      | 1.564e-148           |
