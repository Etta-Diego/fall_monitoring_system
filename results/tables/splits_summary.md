# Participant-level split

Data source: SisFall dataset replay (simulated IoT stream).

Seed 42. SE06 forced to test (75 fall trials; config split.force_test)

| partition   | age_group   |   subjects |   fall |   known_adl |   unknown_adl |
|:------------|:------------|-----------:|-------:|------------:|--------------:|
| train       | elderly     |          9 |      0 |         435 |            85 |
| train       | young       |         15 |   1123 |         883 |           300 |
| val         | elderly     |          3 |      0 |         146 |            30 |
| val         | young       |          4 |    300 |         235 |            80 |
| test        | elderly     |          3 |     75 |         157 |            40 |
| test        | young       |          4 |    300 |         236 |            80 |
