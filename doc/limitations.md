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

_None yet._

## Failure cases (Phase 6)

_Unknown-ADL trials the proposed system still alerted on, and falls it missed. Copied from `results/SUMMARY.md`._
