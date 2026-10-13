---
name: run-eval
description: Run an evaluation round of the AI Engineering Assistant on the demo repository, grade it by hand and record it. Use when asked to evaluate, re-run the evaluation, or measure the effect of a change on answer quality.
---

# Run an evaluation round

## Before starting

- Working tree clean, all tests pass, Ollama up, backend not answering other questions.
- Rebuild saved graphs if graph-building code changed (old graphs in `workspace/graphs/` keep the old resolver).
- Tell Blessy the duration first (full round with Q8 x3 and Q4 x3: 45-75 min; one question: about 4-8 min), that the
  laptop must stay plugged in and awake (power saving once stalled a model call for 2.5 h), and not to use the app
  meanwhile.

## Run (from `backend/`, in the background)

Always pass `--graph`; without it the runner loads the newest saved graph, which may be another repository.

```bash
G=../workspace/graphs/fastapi-realworld-example-app-029eb7781c60.json
.venv/Scripts/python.exe -u ../eval/run_eval.py --graph "$G" --out ../eval/results/roundN
.venv/Scripts/python.exe -u ../eval/run_eval.py --graph "$G" --only Q4 --runs 3 --out ../eval/results/roundN/q4
```

When asked for status, read the log and answer with done / running / remaining and an ETA.

## Grade and record

1. Commit the results exactly as run, before any fix (`eval: round N results as run`).
2. Grade every answer against `eval/questions.json` and the cited lines: ✅ correct, 🟡 mostly, ⚠️ partial, ❌ wrong.
   Verify git-history answers with `git log -L <start>,<end>:<path>` on the function's lines, and check the tool code
   and attempts in `workspace/tools/*/validation.json`; copy that round's generated tools to
   `eval/results/generated-tools/`.
3. Re-check recorded answers with any new checker over all rounds before trusting it (it caught a false positive in
   the path check in round 7).
4. Update `eval/RESULTS.md`: context row, comparison table against the previous rounds, notes per question, and
   regressions or bugs in your own changes stated plainly. Update the README results table and `docs/DEVLOG.md`.
5. Count carefully (round 7 was first written as 4/7 when it was 5/7) and never claim an improvement the transcripts
   do not show. Ask before pushing.
