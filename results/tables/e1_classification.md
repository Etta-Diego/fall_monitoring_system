# E1: known-ADL recognition by the DTE (per decision step)

Frozen config SHA-256: `9b9867ac793ef9c56a5f50ddafd18083936578d1f6fc160605b3b0faf56df956`

Data source: SisFall dataset replay (simulated IoT stream).

Split: test. Accuracy 0.8739, macro F1 0.8412 over 14861 decision steps of known-ADL trials. Classes: coarse activity groups + static (D-009); true class = label of the 3 s window at each step.

| class        |   precision |   recall |   f1-score |    support |
|:-------------|------------:|---------:|-----------:|-----------:|
| walking      |      0.9967 |   0.9971 |     0.9969 |  2730      |
| jogging      |      0.9729 |   1      |     0.9863 |  2728      |
| stairs       |      0.9581 |   0.8539 |     0.903  |  2115      |
| sit_stand    |      0.8375 |   0.6596 |     0.738  |  1610      |
| lying        |      0.9653 |   0.818  |     0.8856 |  1121      |
| bending      |      0.7158 |   0.5765 |     0.6386 |   935      |
| car          |      0.8343 |   0.7753 |     0.8037 |   948      |
| jump         |      1      |   0.7124 |     0.832  |   379      |
| static       |      0.6653 |   0.9621 |     0.7866 |  2295      |
| accuracy     |      0.8739 |   0.8739 |     0.8739 |     0.8739 |
| macro avg    |      0.8829 |   0.8172 |     0.8412 | 14861      |
| weighted avg |      0.8881 |   0.8739 |     0.8736 | 14861      |
