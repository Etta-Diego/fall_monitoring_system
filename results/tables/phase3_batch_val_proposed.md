# Batch replay, proposed mode (val split, development evidence)

Data source: SisFall dataset replay (simulated IoT stream).

Run 20261017T061506-proposed-93e433. val split, known ADLs and falls only (unknown ADLs excluded). A trial counts as alerted if at least one ALERT was emitted. Step OOD rate known 0.3649, fall 0.4729. Latency per decision step: mean 1.88 ms, p95 2.94 ms, max 53.03 ms over 21748 steps.

| activity_group   |   trials |   alerted_trials |   alerts |   alerted_rate |
|:-----------------|---------:|-----------------:|---------:|---------------:|
| fall             |      300 |              288 |      288 |         0.96   |
| known_adl        |      381 |                3 |        3 |         0.0079 |
