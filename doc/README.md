# Thesis documentation (Chapters 4 and 5)

This folder is written **while the system is built**. It holds what you need to write Chapter 4 and Chapter 5 of the thesis: decisions and the reasons for them, verified dataset facts, every result with its source file, limitations, and failure cases.

Generated tables and figures live in `results/`. This folder explains them and says where each one belongs in the thesis.

> Assumed chapter structure (change the guides if your department's template differs):
> - **Chapter 4:** System implementation, testing and results
> - **Chapter 5:** Discussion, summary, conclusion and recommendations

## Files

| File | What it holds | Use it for |
|---|---|---|
| [chapter4_guide.md](chapter4_guide.md) | Suggested Chapter 4 outline + map of every thesis figure/table to its section | Writing Chapter 4 |
| [chapter5_guide.md](chapter5_guide.md) | Suggested Chapter 5 outline, discussion points, recommendations, future work | Writing Chapter 5 |
| [decisions_log.md](decisions_log.md) | Numbered design decisions and deviations from the PRD / Roy et al. | "Implementation details" and justifying choices to the examiner |
| [dataset_notes.md](dataset_notes.md) | SisFall facts checked against the real files and readme | Dataset description, data preparation |
| [experiments_log.md](experiments_log.md) | Every training / tuning / evaluation run with exact numbers and source paths | Results sections |
| [limitations.md](limitations.md) | Limitations, threats to validity, failure cases | Limitations section, Chapter 5 discussion |
| [phase_reports/](phase_reports/) | One report per build phase (what was built, how it was tested, outcome) | Implementation and testing sections |

## Rules these notes follow

- Numbers are copied exactly from generated files, with the file path.
- Each result says which split it came from. **Validation results are development evidence, not final results.** Only Phase 6 test results are headline numbers.
- Data is always described as "SisFall dataset replay (simulated IoT stream)". SisFall falls are "simulated falls from SisFall", never "elderly falls".
