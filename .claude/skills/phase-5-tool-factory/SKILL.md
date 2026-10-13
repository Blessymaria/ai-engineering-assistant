---
name: phase-5-tool-factory
description: Phase 5 of the AI Engineering Assistant - capability gaps, runtime tool generation, static checks, the Docker sandbox, the ctx protocol and tool validation. Use when changing how tools are generated, checked, run or reused (backend/app/toolfactory, backend/app/runner, runner-image).
---

# Phase 5: dynamic tools in a locked-down container

`CLAUDE.md` and `docs/PLAN.md` are the source of truth.

## Rules

- **Generated tools only run inside a throwaway Docker container.** Never `exec` or `eval` generated code in the
  backend process.
- The model writes only the body of a fixed `run(args, ctx)` template, from one worked example, in JSON-schema mode.
- Static check: imports only from `re`, `json`, `collections`, `itertools`, `math`; reject `eval`, `exec`, `compile`,
  `open`, `__import__`, `os`, `sys`, `subprocess`, network modules and any double-underscore name or attribute.
- Container: `docker run --rm -i --network none --read-only --memory 256m --cpus 1 --pids-limit 64 --cap-drop ALL
  --security-opt no-new-privileges`, 10 s timeout, repository not mounted, no secrets.
- `ctx` is the only data path, JSON lines over stdin/stdout: the four core tools, `list_nodes(kind)`, read-only
  `git_log(path, limit)`, `git_log_lines(path, start, end, limit)`, `git_blame(path, start, end)`. Adding a method is a
  deviation from the plan: ask first.
- One retry with the errors; save code and validation record to `workspace/tools/` either way.

## Validation, as learned from evaluation

| Check | Why |
| --- | --- |
| Test inputs use real names from the repository | Invented names (`some_function`) failed every round-1 tool |
| At least one `ctx` read in the test run | A tool returned a hard-coded `count: 12345` and was cited as fact |
| A result containing an `error` key fails | "Not found" results passed silently |
| Function histories may only report commits that changed the function's lines (`git log -L`) | 2 of 3 tools reported the file's last commit |
| A tool for a named function may not require a file path | The agent passed `articles` as a path |
| Non-empty lists are accepted, wrapped as `{"results": [...]}`, as at runtime | A correct `git_log_lines` tool was rejected twice |
| The backend states the newest commit first as `latest_change_verified` | The model picked an older commit from correct blame output |

These checks bound execution and catch known failure modes; they do not prove an arbitrary tool correct. Say so.

## Reuse

Validated tools are kept per repository and commit while the backend runs and offered to later questions (a repeat
history question went from about 3.5 min to 43 s). Restarting the backend clears them; the evaluation runner always
builds a fresh factory so tool creation is measured.

## Done when

`test_toolfactory.py` covers the change, including the real-container tests (skipped without the runner image) and a
regression test with the exact failing case; the exact rejected or wrong tool from its `validation.json` is
re-validated; and a live question on the demo repository gives an answer verified against git.
