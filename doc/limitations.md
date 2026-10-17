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
- **As-specified DTE gives weak OOD separation** (Phase 2, validation). With activity-code labels on every window, still postures shared across activities get low confidence (median 0.45), while post-fall lying is often recognised as D14 with moderate confidence. Val step AUROC known vs fall 0.559; 99.2% of val known-ADL trials have at least one step below 0.9. Source: `phase_reports/phase2_baseline_dte.md`, X-002. Partly resolved by D-009 (grouped + static labels, X-003): AUROC 0.656 per step, 0.620 per trial; but 97.1% of val known-ADL trials still have at least one step below 0.9, mostly at moving-to-still transitions in short sit/stand/lie/bend trials.
- **Baseline uses modified labels** (D-009). The baseline is no longer a strict reproduction of Roy et al.'s per-activity labelling. State this in Chapter 4.5; the as-specified variant is reported for transparency (X-002).
- **High baseline false-alert rate is expected** (Phase 2, validation). Max-softmax confidence at 0.9 flags almost every short known-ADL trial; even at the validation-calibrated threshold 0.49, 67% of val known-ADL trials would alert and 17% of falls would be missed. The headline false-alert reduction will be large partly because the baseline is weak at trial level. Report it with this context, and report the per-step (window-level) rates too, since those are closer to how Roy et al. report results.
- **Baseline often alerts before the fall happens** (Phase 3, validation, X-004). In 44% of val fall trials the first baseline alert comes more than 1.5 s before the impact, while the subject is still doing the pre-fall activity. The PRD's trial-level rule (any alert in a fall trial = detected) counts these as detections, so baseline sensitivity is optimistic. Report alert timing relative to impact alongside sensitivity in Phase 6.

## Failure cases (Phase 6)

_Unknown-ADL trials the proposed system still alerted on, and falls it missed. Copied from `results/SUMMARY.md`._
