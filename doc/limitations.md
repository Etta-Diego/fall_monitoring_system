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
- **Verifier configuration chosen on validation** (Phase 4, X-005). Picked from 2,430 candidates on the same 681 validation trials, so the validation false-alert rate (0.79%) is optimistic. Only test results (Phase 6) should be presented as performance.
- **Rest rule inactive in the selected configuration** (Phase 4, D-013). With a 1.5 s post window the post interval is 0.5 s, too short for `low_activity_s ≥ 1.0 s`; the deployed rule effectively uses impact, orientation and post-impact stillness only.
- **Grid edge** (Phase 4). The selected T_still (0.12 g) is the largest value in the PRD grid.
- **Decision delay** (Phase 4). The proposed system alerts a median 1.84 s after the impact on validation falls (it must wait for post-impact evidence); the baseline's alerts are earlier but often precede the fall.

- **Validation recall did not carry over to test** (Phase 6, X-010). The verifier met fall recall 0.960 on validation but reached 0.803 [0.760, 0.842] on test; the loss vs the baseline is significant (McNemar p = 1.1e-22). Cause: the 3.0 g impact threshold, chosen on 4 young validation subjects, is too high for subjects with softer falls (SA23, and SE06, a judo expert). With only 4–7 subjects per partition, subject-level variation dominates; a different split could give different numbers.
- **Unknown-ADL results rest on 120 trials of 7 subjects**; D13 and D18 come from the 4 young test subjects plus SE06 only.
- **Elderly sensitivity (0.667) comes from one subject**, SE06, whose falls are trained break-falls.

## Failure cases (Phase 6, test split)

Copied from `results/SUMMARY.md`; full lists there.
- **Unknown-ADL trials still alerted on (5):** D11_SA18_R01, D11_SA18_R03, D11_SA18_R04, D11_SA18_R05, D11_SE11_R01 (all "collapse into a chair").
- **Known-ADL trials alerted on (1):** D14_SA11_R05.
- **Falls missed by the proposed system (74):** 35 from SA23, 25 from SE06, 7 SA19, 4 SA18, 3 SA11. By type: F10 13, F13 11, F07 8, F08 8, F14 7, F15 6, F09 5, F03 4, F01 3, F05 2, F06 2, F11 2, F12 2, F02 1, F04 0 (of 25 each). 73 of 74 were examined at the real impact and rejected because the impact peak was below 3.0 g (median 2.17 g).
- **Falls missed by the baseline:** none (but 44.5% of its fall alerts came more than 1.5 s before the impact).
