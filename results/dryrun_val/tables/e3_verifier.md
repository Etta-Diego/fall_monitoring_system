# E3: the verifier on its own (events that reached it, proposed run)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: val (DRY RUN on validation, not a result). 'fall impact' = event in a fall trial whose located impact is within 1 s of the trial's reference impact (argmax Am). Rule columns = pass rate. Confusion (fall impact vs non-fall events): verified/rejected = [[288, 45], [3, 1940]].

| event_type              |   events |   verified |   truncated |   verified_rate |   R_impact |   R_orient |   R_still |   R_rest |
|:------------------------|---------:|-----------:|------------:|----------------:|-----------:|-----------:|----------:|---------:|
| fall impact             |      333 |        288 |           0 |          0.8649 |     0.8979 |     0.982  |    0.9339 |        0 |
| fall trial, other event |      182 |          0 |           3 |          0      |     0.022  |     0.4341 |    0.456  |        0 |
| Known ADLs              |     1943 |          3 |         136 |          0.0015 |     0.0525 |     0.2645 |    0.8569 |        0 |
