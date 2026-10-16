# Limitations, threats to validity and failure cases

Add an entry as soon as a limitation is found. Do not soften it.

## Known before the build (from the PRD)

- **Simulated stream, no hardware.** All data is SisFall dataset replay (simulated IoT stream). Real-device effects (battery, packet loss, sensor placement drift) are not tested.
- **Simulated falls.** SisFall falls were performed by young volunteers (plus, reportedly, one older participant; see `dataset_notes.md` item 9), not real falls of older adults.
- **Baseline is a reimplementation** of Roy et al. (2023) from the paper's description, unless official code is found. Differences go in `decisions_log.md`.
- **Short fall trials** (~15 s) may end before the verifier's post window; such verifications are marked `truncated` and counted in E3.
- **D13 (lie down quickly)** resembles a post-fall posture and is an expected hard case; it is reported per code in E6 and not hand-tuned for.
- **Elderly ADL distribution** differs from young training data, which may raise the OOD rate for elderly subjects; reported in E6.
- **Small test set** at participant level (4 young + 3 elderly by default), so confidence intervals will be wide.

## Found during the build

- **Elderly unknown-ADL coverage is thin** (Phase 1). Elderly subjects other than SE06 never performed D13 or D18 (physician's advice), and SE02 also lacks D10. The E6 elderly subgroup's unknown-ADL results therefore rest mainly on D10 and D11. State this when reporting E6. Source: `dataset_notes.md`.
- **Elderly falls come from one person** (Phase 1). SE06, a judo expert, is the only elderly subject with falls, and is in the test split. Elderly fall sensitivity is based on one subject's 75 trials and should not be generalised.
- **5 trials missing from the dataset** (Phase 1). 4,505 files instead of the readme's 4,510 (SA17 D06 R01; SA20 D06 R02, D17 R02, F01 R03, F10 R04). Minor; see `dataset_notes.md`.

## Failure cases (Phase 6)

_Unknown-ADL trials the proposed system still alerted on, and falls it missed. Copied from `results/SUMMARY.md`._
