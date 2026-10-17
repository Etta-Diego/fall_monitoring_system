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

## Recommendations and future work (added during the build)

Starting points already implied by the PRD's scope:
- Validate on real wearable hardware and on falls from older adults (this work uses simulated falls from SisFall, performed mostly by young volunteers).
- Learned (data-driven) verifier compared with the rule-based one.
- Explainability of alert decisions beyond the rule trace.
- Adapting to the individual user (feedback, personalised thresholds).
- Better-calibrated confidence for the first stage (temperature scaling, energy-based or distance-based OOD scores) instead of raw max-softmax (Phase 2 finding).
- Labelling continuous recordings by motion state (still / transition / activity) rather than one label per trial (Phase 2 finding, D-009).
