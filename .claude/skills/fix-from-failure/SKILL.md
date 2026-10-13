---
name: fix-from-failure
description: Diagnose and fix a wrong or failed answer seen in the app or a screenshot (for example a tool rejected, a wrong commit reported, a misleading label), with a regression test and a live re-run. Use when Blessy shares a screenshot or result and asks what went wrong.
---

# Fix from a failure

## 1. Find the real cause before answering

- Check the claimed facts against the source of truth: git (`git log -L`, `git blame` on the function's exact lines
  from the graph node's `start`/`end`), the source file, or the graph (`query_graph`).
- Read the audit trail: `workspace/tools/<time>-<name|failed>/validation.json` (every attempt, errors, ctx calls,
  test output), the saved answer in `workspace/history.db`, or the SSE events.
- Decide whose fault it is: the model's choice, a tool, or our own validation or UI. Say so plainly. Two of the
  fixes on 9 October were our own bugs (a validation rule too strict, a misleading UI label), not the model's.

## 2. Explain, then propose

Short reply: what happened step by step, what went wrong, the smallest deterministic fix (code beats prompt changes),
and how it will be verified. Ask before changing code.

## 3. Fix

- Make the change in code, keeping validation and runtime consistent.
- Add a regression test that uses the exact failing case (on the demo repository if needed, skipped when it is not
  cloned) plus a test that the existing protection still works.
- Re-validate the exact failing artefact where possible (for example re-run the rejected tool's code from
  `validation.json` through `ToolFactory._validate` with the real container).
- Full test suite, DEVLOG entry (what was found, decision, verification), one commit.
- Restart the backend (`start-app` skill) so the running app uses the fix and has no cached tools.

## 4. Confirm live

Give Blessy the exact question to re-run and the expected answer (verified against git or source beforehand), or run
it through `POST /api/ask` yourself and check the answer, evidence and citations. Only then call it fixed. Ask before
pushing.
