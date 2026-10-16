# SisFall dataset notes

Facts checked against the real dataset files and the official SisFall readme. Each PRD **VERIFY** item gets a row. "Status" is `pending`, `confirmed` or `differs`; if it differs, also add an entry to `decisions_log.md`.

Dataset reference: Sucerquia, A., López, J. D., & Vargas-Bonilla, J. F. (2017). SisFall: A fall and movement dataset. *Sensors*, 17(1), 198.

| # | Item (PRD section) | PRD assumption | Found | How checked | Status |
|---|---|---|---|---|---|
| 1 | Subject folders (5.1) | SA01–SA23 young, SE01–SE15 elderly | | | pending |
| 2 | File name pattern (5.1) | `<ACT>_<SUBJ>_R<TRIAL>.txt` | | | pending |
| 3 | Line format (5.1) | 9 comma-separated ints, ends with `;` | | | pending |
| 4 | Column order (5.1) | ADXL345 xyz, ITG3200 xyz, MMA8451Q xyz | | | pending |
| 5 | Sampling rate (5.1) | 200 Hz | | | pending |
| 6 | Activity counts (5.1) | 19 ADLs, 15 falls | | | pending |
| 7 | ADXL345 conversion (5.2) | ±16 g, 13 bits | | | pending |
| 8 | ITG3200 conversion (5.2) | ±2000 °/s, 16 bits | | | pending |
| 9 | Elderly subject(s) with falls (2.3, 7.1) | SE06 | | | pending |
| 10 | Standing still `Am` ≈ 1 g (Phase 1) | ≈ 1 g | | | pending |
| 11 | Missing ADL files for elderly (5.1) | some missing | | | pending |

## Participant demographics

_To fill from the readme: age range, sex, height, weight per group._

## Other observations

_Anything unexpected in the files (corrupt lines, odd trial lengths, extra activities)._
