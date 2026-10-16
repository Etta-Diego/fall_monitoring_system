# CLAUDE.md

@AGENTS.md

The shared rules for every agent are in [AGENTS.md](AGENTS.md), imported above. The full spec is [fall-monitoring-PRD.md](fall-monitoring-PRD.md). The notes below are specific to Claude Code.

## Working style for this repo

- **One phase per session of work.** Before starting a phase, re-read its PRD section (Section 14 plus the sections it references) and the current `doc/decisions_log.md`. Use a todo list for the phase's acceptance checks.
- **End-of-phase routine** (in this order):
  1. Run `pytest` and the phase's acceptance checks. Show the real output.
  2. Write `doc/phase_reports/phaseN_<name>.md` from `doc/phase_reports/_template.md`.
  3. Update `doc/experiments_log.md`, `doc/decisions_log.md`, `doc/limitations.md` and the artefact map in `doc/chapter4_guide.md` as needed.
  4. Stop and give the developer a short report: what was built, check results, anything that failed or deviated, open questions. Wait for the go-ahead.
- **VERIFY items:** inspect the real files (`head`, a small Python snippet) before writing loader or config code. If the dataset is not in `data/raw/SisFall_dataset/` yet, stop and ask the developer to place it. Do not code against guessed formats.
- **Test split:** do not open, load, window, plot or summarise test-split trial *contents* before Phase 6. Counting files per subject for the dataset summary and split is fine.
- **Long jobs** (training, grid search, full evaluation): run in the background and keep working or wait for the notification; don't poll.
- **Git:** commit only when the developer asks. Never commit `data/raw/`, `data/processed/`, model weights, `.env` or `logs/`. Do commit `data/splits.json` once generated.
- **Filename note:** the PRD's layout calls the spec `PRD.md`; in this repo it is `fall-monitoring-PRD.md`. Don't rename it unless asked.

## When unsure

If the PRD is silent or ambiguous, pick the option that best protects fairness of the baseline vs proposed comparison and the leakage rules, note it in `doc/decisions_log.md`, and mention it in the phase report. Ask only when the choice changes results or scope.
