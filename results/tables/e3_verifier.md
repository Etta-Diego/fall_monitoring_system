# E3: the verifier on its own (events that reached it, proposed run)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. 'fall impact' = event in a fall trial whose located impact is within 1 s of the trial's reference impact (argmax Am). Rule columns = pass rate. Confusion (fall impact vs non-fall events): verified/rejected = [[298, 162], [6, 2206]].

| event_type              |   events |   verified |   truncated |   verified_rate |   R_impact |   R_orient |   R_still |   R_rest |
|:------------------------|---------:|-----------:|------------:|----------------:|-----------:|-----------:|----------:|---------:|
| fall impact             |      460 |        298 |           0 |          0.6478 |     0.6652 |     0.9978 |    0.9239 |        0 |
| fall trial, other event |      333 |          3 |          10 |          0.009  |     0.012  |     0.3874 |    0.4775 |        0 |
| Known ADLs              |     1783 |          1 |         119 |          0.0006 |     0.074  |     0.2574 |    0.88   |        0 |
| Unknown ADLs            |      429 |          5 |          36 |          0.0117 |     0.1096 |     0.2914 |    0.7949 |        0 |
