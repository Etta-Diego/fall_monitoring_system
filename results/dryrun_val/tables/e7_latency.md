# E7: processing latency per decision step

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). Time from receiving the raw sample that completes a decision step to the decision being produced (preprocessing of that sample + DTE inference + event logic + verification when due); database and notification I/O excluded (D-010). Decision interval 0.5 s. CPU only.

| system   |   decision_steps |   mean_ms |   median_ms |   p95_ms |   p99_ms |   max_ms |
|:---------|-----------------:|----------:|------------:|---------:|---------:|---------:|
| baseline |            21748 |     1.784 |       1.574 |    2.623 |    4.217 |  182.18  |
| proposed |            21748 |     1.836 |       1.658 |    2.821 |    3.809 |   56.335 |
