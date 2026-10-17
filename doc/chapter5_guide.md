# Chapter 5 guide: discussion, conclusion and recommendations

Agents add points here as they come up during the build. Each point should link to its evidence (a results file, a decisions or limitations entry).

## Suggested outline

**5.1 Summary of the work**: what was built and how it was evaluated, in one or two paragraphs.

**5.2 Discussion of findings**: answer the research question directly:
- How much did verification reduce false alerts overall, on known ADLs, and on unseen fall-like ADLs? (E4, E6)
- What did it cost in fall sensitivity? Is the difference significant (McNemar, CIs)? (E4)
- What did it cost in decision delay and processing latency? Is it still "real time"? (E4, E5, E7)
- Which rules did the work? Which features separated falls from fall-like ADLs, and which did not? (E3)
- Hard cases (expected: D13 lie down quickly) and failure cases from `results/SUMMARY.md`.
- How the baseline compares with the numbers reported by Roy et al. (2023), and why it may differ.

**5.3 Achievement of objectives**: one row per thesis objective: met / partly met / not met, with evidence.

**5.4 Contribution to knowledge**

**5.5 Limitations**: from `limitations.md`.

**5.6 Conclusion**

**5.7 Recommendations and future work**: from the list below.

## Discussion points (added during the build)

- **Why an impact threshold alone cannot work** (Phase 1, `results/figures/phase1_examples.png`, train subject SA01). The unknown ADL D10 (quickly sit in a low chair) reaches ~3.2 g `Am`, above the PRD's starting impact threshold of 2.5 g, so impact alone would raise a false alarm. What separates it from the fall F01 (~9 g peak) is what happens *after*: in D10 the person moves again within ~4 s (stands up), while after the fall the signal goes flat (lying still). This is the motivation for checking post-event windows (orientation, stillness, rest) instead of the impact alone. Check whether E3 on the test split confirms this pattern before claiming it.
- **Low confidence is not specific to falls** (Phase 2, validation, X-002). The as-specified DTE gives low max-softmax confidence to ordinary still postures (standing/sitting still inside sit-down and bending activities: median 0.45) because the same posture appears under several activity labels. Meanwhile, the still part of a fall (lying) is often recognised as a known lying activity (D14). This is direct evidence for the thesis gap: treating low confidence as a fall produces false alarms even on *known* activities. Use with care: report the final, test-split numbers, and state which baseline variant they come from.
- **Relabelling helps recognition more than OOD detection** (Phase 2, X-002 vs X-003). Coarse groups + a static class raised known-activity macro F1 from 0.694 to 0.819 and trial-level fall separation from AUROC 0.380 to 0.620, but nearly all short known-ADL trials still dip below 0.9 at moving-to-still transitions. Discussion angle: the weakness lies in using max-softmax confidence on its own as the fall signal, not only in the labels. This motivates a second stage that looks at the physical event itself.
- **Trial-level vs window-level reporting** (Phase 2). Roy-style OOD is usually reported per window; a monitoring system is judged per activity episode (did it alert or not). The same detector looks far worse per episode (97% of known trials with ≥1 OOD step vs 36.5% of steps). Worth a paragraph when comparing with published numbers.
- **"Detected" is not the same as "detected at the right time"** (Phase 3, X-004). The baseline flags every val fall trial, but 44% of those first alerts come more than 1.5 s before the impact, triggered by the pre-fall activity rather than the fall. Discuss whether trial-level sensitivity is a fair measure for a fall alarm, and use the decision-delay results (E4) to show when alerts actually happen.
- **One check per event is not enough** (Phase 4, X-005, D-012). With the verifier running once per OOD event (as first specified), no configuration kept fall recall at 0.95 on validation (best 0.65), because the low-confidence event often starts during the pre-fall activity and the real impact comes later. Ending a rejected event and re-checking (re-arm) restored recall to 0.96 while keeping false alerts under 1% on validation. A useful design lesson for any two-stage alarm: verification must be anchored to the physical event, not to when the first stage became unsure.
- **Which evidence separates falls from fall-like activity** (Phase 4, validation rule pass rates). Among events reaching the verifier, the impact rule passed for 5% of known-ADL events vs 59% of fall-trial events; orientation change 26% vs 79%; post-impact stillness 86% vs 77% (people are often still after normal activities too, so stillness alone separates poorly). Confirm with E3 on the test split.
- **Cost of verification is time** (Phase 4). The proposed alert comes a median 1.84 s after the impact on validation (baseline −1.23 s, i.e. often before the fall). Discuss whether ~2 s is acceptable for elderly-care response, where help typically takes minutes.

### Final (test split) discussion points, Phase 6 (X-010)
- **Answer to the research question.** Post-event temporal verification cut false alerts by 99.0% (618 → 6; 225.8 → 2.19 per hour), including on unseen fall-like activities (FPR unknown 1.000 → 0.042). The cost was sensitivity, 1.000 → 0.803, and about 1.9 s of decision delay after the impact (median), with ~0.2 ms extra processing per decision. Both differences are statistically significant (McNemar).
- **Is the trade-off worth it?** At 225.8 false alerts per hour the baseline is unusable as an alarm (it alerts on 96% of normal trials), so its "100% sensitivity" has little practical value; also 44.5% of its fall alerts came before the fall. The proposed system is usable in principle but misses one fall in five here. Discuss which error is worse in elderly care (missed fall vs alarm fatigue), and that a missed fall in a real deployment has serious consequences.
- **Why recall dropped from validation to test.** 73 of 74 missed falls were rejected only because the impact was below 3.0 g (median 2.17 g); orientation and stillness evidence was present. Misses cluster in two subjects (SA23 47%, SE06 33% missed) and in low-energy fall types (falls while sitting down or from sitting). The threshold was chosen on 4 validation subjects with harder falls: a small-sample generalisation problem, made visible because the test split was held out properly.
- **SE06 is a judo expert**: trained break-falls reduce impact, so the elderly-subgroup sensitivity (0.667) says more about this one person than about older adults.
- **Remaining false alerts are physically fall-like.** 5 of 6 are D11 "collapse into a chair", which has an impact and a posture change. Rules based on impact/orientation/stillness cannot fully separate these; context (e.g. a chair) or more features would be needed.
- **Confidence alone is weak** (E2): per-step AUROC 0.684 (falls) and 0.634 (unknown ADLs); per trial, unknown ADLs are not less confident than known ADLs (AUROC 0.420). This supports the thesis claim that OOD confidence needs a second, physical check.
- **The rest rule never contributed** (D-013); the effective verifier used impact + orientation + stillness.

## Recommendations and future work (added during the build)

Starting points already implied by the PRD's scope:
- Validate on real wearable hardware and on falls from older adults (this work uses simulated falls from SisFall, performed mostly by young volunteers).
- Learned (data-driven) verifier compared with the rule-based one.
- Explainability of alert decisions beyond the rule trace.
- Adapting to the individual user (feedback, personalised thresholds).
- Better-calibrated confidence for the first stage (temperature scaling, energy-based or distance-based OOD scores) instead of raw max-softmax (Phase 2 finding).
- Make the impact rule adaptive or less dominant: e.g. lower or subject-normalised impact thresholds, or allow strong orientation + stillness evidence to verify without a hard impact; choose it with more validation subjects (Phase 6: 73/74 misses were sub-threshold impacts).
- Use cross-validation over subjects (or more subjects) when tuning, so thresholds do not depend on a few people (Phase 6).
- Revisit the post-interval design so the rest rule can contribute at short post windows (e.g. start the post interval earlier), chosen on validation data (Phase 4, D-013).
- Labelling continuous recordings by motion state (still / transition / activity) rather than one label per trial (Phase 2 finding, D-009).
