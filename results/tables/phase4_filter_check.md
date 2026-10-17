# Causal vs zero-phase filter check (validation split)

Data source: SisFall dataset replay (simulated IoT stream).

Models were trained on causally filtered data (D-003) and are NOT retrained here; the zero-phase column shows the effect of feeding zero-phase input to the same models. Peak time shift is at 50 Hz resolution (20 ms per sample).

| check                                                        |   causal |   zero_phase |
|:-------------------------------------------------------------|---------:|-------------:|
| causal filter group delay at 1 Hz [ms]                       |  20.13   |       0      |
| causal filter group delay at 2 Hz [ms]                       |  20.2    |       0      |
| causal filter group delay at 5 Hz [ms]                       |  20.75   |       0      |
| causal filter group delay at 10 Hz [ms]                      |  23.32   |       0      |
| step OOD rate, known ADLs                                    |   0.3649 |       0.364  |
| step OOD rate, falls                                         |   0.4729 |       0.473  |
| AUROC known vs fall (per step)                               |   0.6556 |       0.6565 |
| mean |confidence difference| per step                        |   0      |       0.009  |
| fall impact peak Am, median [g]                              |   6.4928 |       6.2532 |
| fall impact peak time shift causal - zero-phase, median [ms] |  20      |       0      |
| fall impact peak time shift, max |shift| [ms]                | 400      |       0      |
