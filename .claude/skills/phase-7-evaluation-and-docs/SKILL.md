---
name: phase-7-evaluation-and-docs
description: Phase 7 of the AI Engineering Assistant - the evaluation question set, results, README, DEVLOG and assumptions and limitations. Use when writing or updating the evaluation, README, DEVLOG or RESULTS, or when closing a piece of work.
---

# Phase 7: evaluation and documentation

`CLAUDE.md` and `docs/PLAN.md` are the source of truth. Running a round: `run-eval` skill. Shared reports and
screenshots: `project-report` skill.

## Evaluation design

- Eight questions on `fastapi-realworld-example-app` @ `029eb77`: structure, nonexistent symbol, flow, runtime-only
  data, dependencies, implementation, documentation, and a git-history gap run three times.
- Expected facts are written from the source and git history and committed **before** any run (`d85885e`).
- Every answer is graded by hand against those facts and the cited lines. Each round is committed exactly as it ran,
  before any fix; fixes address only what the evaluation exposed, never a question's wording.
- Uncertainty cases are part of the set (a symbol that does not exist, data only the running system knows).

## Documentation rules

- **DEVLOG** (`docs/DEVLOG.md`), one entry per commit-worthy step:
  `## <date> — <phase>: <what was done>` then Changes / Decisions / Verified / Issues-next. Record decisions,
  deviations and failures honestly, including bugs in our own changes.
- **README**: setup, running, evaluation table, deviations from the plan, assumptions and limitations. Update it in
  the same commit as the behaviour it describes.
- **RESULTS** (`eval/RESULTS.md`): context per round, comparison tables, notes per question, generated tools.
- After code changes, update repository files only; shared documents and speaker notes change only when asked.
- No Claude or Anthropic attribution anywhere.

## Commits and pushes

- Small steps, tests passing, clear messages (`feat(graph): ...`, `fix(toolfactory): ...`, `docs: ...`).
- Ask before pushing; Blessy approves each batch. Ask before anything destructive (force-push, deleting branches).
- When asked what was done, summarise by outcome with commit hashes, and list what is still open.
