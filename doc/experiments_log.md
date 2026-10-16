# Experiments log

Every training, tuning and evaluation run that produced numbers. Newest at the bottom. Copy numbers exactly from the source file.

Entry format:

```
## X-NNN: <run name>
- Date / phase:
- Command:
- Split(s) used:
- Config / hash: (git commit, frozen hash for test runs)
- Machine: (CPU, RAM, OS; once is enough unless it changes)
- Key results: (small table, exact values)
- Source files:
- Notes: (anything surprising; link to limitations.md if relevant)
```

---


## X-001: Data preparation
- Date / phase: 2026-10-16 / Phase 1
- Command: `fallmon prepare-data`
- Split(s) used: index of all subjects (file counts only); conversion check and example plot use train subjects only.
- Config / hash: base commit 327a268 (Phase 1 uncommitted), seed 42
- Machine: Linux 6.8.0-138-generic, Python 3.10.12, CPU only
- Key results: 4,505 trial files, 38 subjects; split train 24 / val 7 / test 7 subjects; standing Am over 120 train D07 trials mean 1.009 g (min 0.967, max 1.097); run time ~10 s.
- Source files: `data/processed/index.parquet`, `data/splits.json`, `results/tables/dataset_summary.*`, `results/tables/splits_summary.*`, `results/figures/phase1_examples.png`
- Notes: 5 SA15 files carry the SE15 name; folder used (D-005).
