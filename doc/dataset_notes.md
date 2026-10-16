# SisFall dataset notes

Facts checked against the real dataset files and the official SisFall readme. Each PRD **VERIFY** item gets a row. "Status" is `pending`, `confirmed` or `differs`; if it differs, also add an entry to `decisions_log.md`.

**Cite in the thesis (not the mirror):** Sucerquia, A., López, J. D., & Vargas-Bonilla, J. F. (2017). SisFall: A fall and movement dataset. *Sensors*, 17(1), 198. https://doi.org/10.3390/s17010198

## Source of the copy used

- Obtained from the GitHub mirror `Fall-Prevention-Team/sisfallData`, commit `8352a0fe6c8c73e3d0af3619dc772cf8200b3e53` (2022-02-25), cloned 2026-10-16 into `data/raw/SisFall_dataset/`.
- Cross-checked against the Hugging Face mirror `Trupal7/Sisfall_Dataset` (`SisFall_dataset.zip`, 232,407,821 bytes): **same file list**, same 5 missing files and same SA15/SE15 naming quirk. So these properties come from the original distribution, not from a broken mirror.
- Readme: `Readme.txt` (Version 1.0, February 2016), Latin-1 encoded.

## VERIFY checklist

| # | Item (PRD section) | PRD assumption | Found | How checked | Status |
|---|---|---|---|---|---|
| 1 | Subject folders (5.1) | SA01–SA23 young, SE01–SE15 elderly | Exactly these 38 folders | `ls` | confirmed |
| 2 | File name pattern (5.1) | `<ACT>_<SUBJ>_R<TRIAL>.txt` | All files match `^[DF]\d{2}_S[AE]\d{2}_R\d{2}\.txt$`. **But 5 files in `SA15/` are named `D17_SE15_R01..05`** (see below) | regex over all files | confirmed (with quirk) |
| 3 | Line format (5.1) | 9 comma-separated ints, ends with `;` | 9 ints per line. **2 files (`SA01/D01_SA01_R01`, `SA01/D02_SA01_R01`) have no `;` on any line.** 17 files end with a trailing blank line. No other anomalies. | parsed every line of every file | confirmed (with quirks) |
| 4 | Column order (5.1) | ADXL345 xyz, ITG3200 xyz, MMA8451Q xyz | Same, per readme | readme | confirmed |
| 5 | Sampling rate (5.1) | 200 Hz | 200 Hz per readme; trial lengths (e.g. 12 s = 2400 rows) agree | readme + row counts | confirmed |
| 6 | Activity counts (5.1) | 19 ADLs, 15 falls | 19 ADLs (D01–D19), 15 falls (F01–F15) | readme + file names | confirmed |
| 7 | ADXL345 conversion (5.2) | ±16 g, 13 bits | ±16 g, 13 bits. Formula `[(2*Range)/(2^Resolution)]*AD` | readme | confirmed |
| 8 | ITG3200 conversion (5.2) | ±2000 °/s, 16 bits | ±2000 °/s, 16 bits. Same formula | readme | confirmed |
| 9 | Elderly subject(s) with falls (2.3, 7.1) | SE06 | SE06 only ("expert in Judo"); has all 15 falls × 5 trials and all 19 ADLs | readme + inventory | confirmed |
| 10 | Standing still `Am` ≈ 1 g (Phase 1) | ≈ 1 g | First 1 s of D07 (standing): SA01 1.018 g, SA05 0.969 g, SE03 0.998 g (std < 0.01 g) | conversion on raw files | confirmed |
| 11 | Missing ADL files for elderly (5.1) | some missing | All elderly except SE06 lack D06, D13, D18, D19 (physician's advice, per readme). SE02 also lacks D04, D09, D10. SE15 also lacks D04. | inventory | confirmed |

## File count: 4,505, not 4,510

The readme says 4,510 files; both mirrors have **4,505**. The 5 trials missing compared with the full protocol are all from young subjects:

| Missing file | Subject | Activity |
|---|---|---|
| D06_SA17_R01 | SA17 | D06 (stairs quickly) |
| D06_SA20_R02 | SA20 | D06 |
| D17_SA20_R02 | SA20 | D17 (car) |
| F01_SA20_R03 | SA20 | F01 (fall) |
| F10_SA20_R04 | SA20 | F10 (fall) |

Effect: SA20 has 73 fall trials instead of 75. The loader works from the files actually present, so nothing else is needed.

## SA15 / SE15 naming quirk

`SA15/` contains `D17_SE15_R01.txt` … `D17_SE15_R05.txt`, and SA15 has no file named `D17_SA15_*`. `SE15/` has its own, **different** `D17_SE15_R01..05` files (different checksums; 5000 vs 4999/5000 rows). So these are SA15's D17 (get into a car) recordings with the wrong subject ID in the filename. The loader takes the subject from the **folder**, not the filename (decision D-005).

## Trial durations (rows / 200 Hz, min / median / max)

- D01–D04: 100 s median, but some trials are 180 s (max 180.0 s).
- D05, D06: 25 s. D07–D16, D18, D19: 12 s (D11, D15, D16 have a few 10 s trials).
- D17: 16–27 s (median 25 s).
- Falls F01–F15: 15 s (shortest 14.5 s). This matters for the verifier's post window (PRD risk table).

## Participant demographics (from readme)

| Group | n | Age range | Sex |
|---|---|---|---|
| Young (SA) | 23 | 19–30 | 12 F, 11 M |
| Elderly (SE) | 15 | 60–75 | 7 F, 8 M |

Per-subject age, height (cm), weight (kg) and sex are in the readme table and can be reproduced in an appendix.

## Consequences for the thesis

- **Unknown ADLs in the elderly subgroup.** D13 and D18 were never recorded for elderly subjects (except SE06), and SE02 has no D10. So in E6 the elderly unknown-ADL results rest almost entirely on D10 and D11. Recorded in `limitations.md`.
- **Elderly falls = one person.** Only SE06 (a judo expert) has elderly fall trials; per PRD SE06 is forced into the test split.
