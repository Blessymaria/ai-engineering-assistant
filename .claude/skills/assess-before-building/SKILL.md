---
name: assess-before-building
description: Assess a requested change or improvement list before writing any code - confirm which problems are real, say what is feasible and what is actually necessary, estimate the time, and wait for approval. Use whenever Blessy asks for improvements, fixes, new features or a review against requirements, especially a long pasted brief.
---

# Assess before building

Blessy's standing instruction: "ask before doing any task, let me know what all are feasible and what you think is
necessary - do not listen plainly; see what's effective for the project and right, and then do." A pasted brief is a
starting point, not a work order.

## 1. Inspect first, change nothing

- Read the code that is actually involved, the tests, `eval/RESULTS.md` and the latest entries in `docs/DEVLOG.md`.
- Reproduce or measure each claimed problem from evidence: evaluation transcripts in `eval/results/`, audit records
  in `workspace/tools/*/validation.json`, saved answers in `workspace/history.db`, git (`git log -L`, `git blame`).
- Separate: confirmed and still reproducible / already fixed / not a real problem.

## 2. Reply with an assessment, not code

For each item: what is confirmed, the root cause, the smallest fix, and a verdict.

| # | Change | Size | Verdict |
| --- | --- | --- | --- |
| 1 | ... | small / medium / 1-2 h of laptop time | Do / Investigate first / Skip (why) |

- Push back where something is unnecessary or counter-productive (for example more prompt tuning, which traded one
  behaviour for another in evaluation round 5) and say why in one line.
- Call out anything that deviates from `CLAUDE.md` or `docs/PLAN.md` (new `ctx` methods, new infrastructure) and ask
  for that approval explicitly.
- If asked "what difference does this make", answer per question type with expected outcomes, and say what will NOT
  change. These are predictions; the evaluation measures them.
- Give a time estimate before anything long ("review 15-25 min; fixes 0-45 min; evaluation 1-2 h"), and wait.

## 3. After approval

- Implement in the approved order, one commit per step, each with tests; run the full suite (`pytest`, frontend
  `npm.cmd run build` and `npm.cmd run lint`) before every commit.
- Measure before and after with the evaluation where answers are affected (`run-eval` skill).
- If a step turns out smaller or different than assessed (for example a "wasted round" that only costs 10 s), say so
  and do not change it just to have done something.
- Final report: what changed and why, files, tests added, before/after numbers including regressions, remaining
  limitations, what was deliberately deferred. Then ask before pushing.
