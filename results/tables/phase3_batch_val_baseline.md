# Batch replay, baseline mode (val split, development evidence)

Data source: SisFall dataset replay (simulated IoT stream).

Run 20261017T055454-baseline-765f17. val split, known ADLs and falls only (unknown ADLs excluded). A trial counts as alerted if at least one ALERT was emitted. Step OOD rate known 0.3649, fall 0.4729. Latency per decision step: mean 1.75 ms, p95 2.59 ms, max 61.29 ms over 21748 steps.

| activity_group   |   trials |   alerted_trials |   alerts |   alerted_rate |
|:-----------------|---------:|-----------------:|---------:|---------------:|
| fall             |      300 |              300 |      320 |         1      |
| known_adl        |      381 |              370 |      496 |         0.9711 |
