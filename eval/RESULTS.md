# Evaluation results

Eight questions on [fastapi-realworld-example-app](https://github.com/nsidnev/fastapi-realworld-example-app), each with its expected facts written from the source and git history **before** any run ([questions.json](questions.json), committed in `d85885e`). Every answer was checked by hand against those facts and against the cited source lines. Full transcripts, every step and all evidence are in [results/](results/).

## Context

| | |
| --- | --- |
| Model | `gemma4:e4b` via Ollama **0.35.0**, temperature 0 (Ollama updated itself from 0.34.4 on 2026-09-30 at 11:19, before round 1; the phase 1-5 runs in the devlog used 0.34.4) |
| Hardware | Intel Core Ultra 5 225U, 32 GB RAM, CPU only (no GPU), Windows 11 |
| Demo repository | `fastapi-realworld-example-app` @ `029eb7781c60d5f563ee8990a0cbfb79b244538c` (full history, 209 commits) |
| Round 1 | assistant @ `d85885e`, run 2026-09-30 11:56 |
| Round 2 | assistant @ `4c5d0a2` (three fixes found by round 1), run 2026-09-30 12:42 (resumed at 13:20 after a stalled model call) |
| Round 3 | assistant @ `7cf9241` (fix found by round 2), Q4 only, run 2026-09-30 14:20 |
| Round 4 | assistant @ `c3bae7c` (runtime-data prompt rule, stop button, path limits), Q4 ×3, run 2026-09-30 |
| Round 5 | assistant @ `bcdbf97` (citation check, unconfirmed-calls list, prompt tightening), all questions, Q4 and Q8 ×3, run 2026-09-30 |
| Round 6 | assistant @ `edf38a3` (repository gap vs runtime state in the prompt), Q8 ×3 and Q4 ×3, run 2026-09-30 |
| Round 7 | assistant @ `cfb397e` (reliability fixes: `ctx.git_log_lines`, tool answer checks, typed-call resolution, location and path checks, tool reuse), all questions, Q8 ×3 and Q4 ×3 more, run 2026-10-08 on Ollama **0.35.1**; Q1 run again @ `ac5aaa2` after a bug fix the round exposed |

Each round was recorded exactly as it ran and committed before any fix (`ad73a2d` round 1, `5dfbb7b` round 2). Fixes between rounds were for bugs the evaluation exposed; nothing was tuned to a specific question's wording.

## Results

Verdicts: ✅ correct · 🟡 mostly correct (a minor fact missing) · ⚠️ partial (key facts missing or one wrong detail) · ❌ wrong.

| # | Type | Round 1 | Round 2 | Round 3 |
| --- | --- | --- | --- | --- |
| Q1 | Structure | ⚠️ Right packages and roles, but 0 citations, invents an `app/db/models/` folder, hedges ("likely") | ⚠️ Same: 0 citations, same invented folder | |
| Q2 | Nonexistent symbol | ✅ Says it is not found; points to the real `delete_article_by_slug` / `delete_article`, clearly labelled; invents nothing | ✅ Same | |
| Q3 | Flow | ⚠️ Correct handler, then passes a file path to `query_graph` twice (errors) and stops without following the calls | 🟡 Full route-level flow in order: slug, existence check, 400, `create_article`, `ArticleInResponse`, each call line cited correctly; does not flag the injected repository call as unconfirmed or go inside the repository | |
| Q4 | Runtime-only | ⚠️ Invents no number, but never says static analysis cannot know it | ❌ **Fabricated: "12,345 articles [E4]"**, from a generated tool that returned a hard-coded value (see below) | ⚠️ No number invented, no gap reported, so no tool was generated (the new check was **not exercised** in this run; it is covered by its regression test). Still does not say static analysis cannot know this, and misreads search hits as "`SELECT COUNT(*) FROM articles` was found in multiple places" |
| Q5 | Dependencies | ✅ All 6 importing modules, cited | ✅ Same | |
| Q6 | Implementation | ⚠️ Creation correct (`jwt.py:15/27/35`); where it is checked not found | ✅ Creation, then the check path: Authorization header and prefix in `_get_authorization_header`, `jwt.get_username_from_token` at `dependencies/authentication.py:84`, user lookup | |
| Q7 | Documentation | ❌ Says the README does not explain tests (it does, at line 74) | 🟡 Finds "Run tests" (`README.rst:74-86`): tests in `tests/`, run `pytest`; omits the `DATABASE_URL` setup step | |
| Q8 ×3 | Gap: git history | ❌ 3/3 gap reported, 0/3 tools created (all tested on invented names and rejected); honest "cannot determine" | Tools created 3/3; **correct 1/3**: run 1 Nik, 2020-05-01 ✅; runs 2-3 report the file's last commit (dependabot, 2020-09-02), which did not touch `create_article` ❌ | |

| Summary | Round 1 | Round 2 |
| --- | --- | --- |
| Correct or mostly correct (Q1-Q7) | 2 / 7 | 5 / 7 |
| Citation references valid | 8 / 8 | 12 / 12 |
| Cited lines that say what the answer claims (checked by hand) | all checked | all checked |
| Q8 tool created / correct answer | 0 / 3, 0 / 3 | 3 / 3, 1 / 3 |
| Tools created when not needed | 0 | 1 (Q4, fabricated) |
| Total model time | 29 min | 61 min (incl. one 27-min stall) |

### Round 4: Q4 three times, after adding a runtime-data rule to the prompt (`c3bae7c`)

| Run | Invented a number | Reported a gap / built a tool | Said it cannot be known from code |
| --- | --- | --- | --- |
| 1 | No | No | Partly: "cannot determine the total number ... from the code provided", but because no count function was found |
| 2 | No | No | No: says a count function "would be required", as if code could answer it |
| 3 | No | No | No: same as run 2 |

The rule stopped fabrication and unnecessary tool creation (3/3), but not the framing: gemma4:e4b treats "how many are stored?" as "is there a function that counts them?".

### Rounds 5 and 6: after the final review's improvements

Round 5 added, in code: an answer with no (valid) citations goes back once for a rewrite; ambiguous and unresolved calls the agent visited are listed under the answer from the evidence. In the prompt: a fixed opening sentence for runtime-state questions, "only name files seen in tool results", and, for the tool writer, "work on the symbol's own lines".

| # | Round 2 | Round 5 | Round 6 |
| --- | --- | --- | --- |
| Q1 Structure | ⚠️ 0 citations, invented folder | ⚠️ Now cited (the citation check works), still invents `app/db/models/` | - |
| Q2 Nonexistent symbol | ✅ | ✅ | - |
| Q3 Flow | 🟡 | 🟡 Route-level flow, all call lines cited; did not use `query_graph`, so no diagram or unconfirmed-calls list | - |
| Q4 Runtime-only (×3 from round 4) | ❌ fabricated | ⚠️ 0/3 invented; 2/3 end "cannot determine ... from the source code", but because no count function was found | ⚠️ 0/3 invented; none use the prescribed sentence; 2/3 say the endpoint would have to be run |
| Q5 Dependencies | ✅ | ✅ | - |
| Q6 Implementation | ✅ | ⚠️ Creation correct; where the token is checked not found (repeated searches) | - |
| Q7 Documentation | 🟡 | 🟡 | - |
| Q8 Gap reported / tool created / correct | 3/3, 3/3, 1/3 | **0/3, 0/3, 0/3 (regression)** | **3/3, 3/3, 1/3** |

**The round 5 regression and its fix.** The new runtime-state rule said not to report a capability gap, and the prompt opened with "you have the source code only"; the model applied both to git history and answered "outside the scope of the tools" three times. Round 6 separates the two cases explicitly (information in the repository that no tool reads yet → report a gap; state of the running application → cannot be known) and the gap was reported 3/3 again.

**Round 6, Q8 in detail:** run 2's tool blamed the function's own lines and took the newest date: correct (Nik, 2020-05-01). Runs 1 and 3 made tools that need a file path, and the agent passed `articles` (from "the articles repository" in the question); the tool refused a path that does not exist, and the agent asked the user for the path instead of looking it up. No fabrication, but no answer.

**Where this leaves things:** the safety measures held in every run after they were added (no invented value in the 10 runtime-question runs since round 3; since round 5 every answer that had evidence cites it; invalid paths refused). What did not improve with more prompt changes is how well the small model writes and uses tools, and whether it frames runtime questions correctly; each prompt change traded one behaviour for another. These are recorded as limitations rather than tuned further.

### Round 7: reliability fixes (2026-10-08)

Changes since round 6, all in code (no prompt tuning for specific questions; the one prompt change describes the new `ctx` method):

1. `ctx.git_log_lines(path, start, end)`: the history of a line range (`git log -L`), so a tool gets one function's history in one call instead of combining blame lines or (wrongly) using the file's log.
2. Tool test checks: a tool whose output reports commits for a named function is rejected if those commits did not change the function's lines (checked with `git log -L`); a tool for a gap that names a function may not require a file path the agent does not have.
3. The call resolver resolves calls on parameters annotated with a repository class and on attributes set from a class in `__init__`; ambiguous calls in the demo graph went from 103 to 76 (itsdangerous 212 to 157), and `query_graph` now follows POST /articles into the repository (unit test `test_demo_flow_follows_the_injected_repository`).
4. Answer checks: every cited `file:line` must exist and lie inside its evidence; every file or folder named must exist; a failing answer gets one rewrite, and what remains is shown with it.
5. Validated tools are reused for later questions on the same repository and commit (not in the evaluation runner, which builds a fresh factory per run, so tool creation is measured every time).

| # | Rounds 5-6 (baseline) | Round 7 | Notes |
| --- | --- | --- | --- |
| Q1 Structure | ⚠️ invents `app/db/models/` | 🟡 correct packages and subpackages, nothing invented; `tests/` not mentioned | Run again after the fix below: the model **wrote `app/db/models/` again** in its first draft; the path check caught it and the one rewrite removed it |
| Q2 Nonexistent symbol | ✅ | ✅ | |
| Q3 Flow | 🟡 | 🟡 same route-level flow, every call line cited | **Not improved**: the model asked `query_graph` for the handler's *callers* instead of its callees, so the better graph was never used; no diagram |
| Q4 Runtime-only (×4) | ⚠️ 0/6 invented; 0/6 used the prescribed sentence | ⚠️ 0/4 invented; 1/4 used the prescribed sentence and 1/4 said it depends on the live database; 2/4 still look for a counting function | Nothing changed for this; run-to-run variation |
| Q5 Dependencies | ✅ | ✅ all 6 modules | |
| Q6 Implementation | ⚠️ | ⚠️ creation correct and cited; says the token is checked in `app/api/routes/users.py` (where the dependency is used) instead of `app/api/dependencies/authentication.py` | |
| Q7 Documentation | 🟡 | 🟡 `pytest`, `tests/` folder; omits `DATABASE_URL` | |
| Q8 Gap: git history (×3) | 3/3 gap, 3/3 tool, **1/3 correct** (round 6) | 3/3 gap, 3/3 tool, **3/3 correct**: Nik, 2020-05-01, `155ac54` | All three first attempts required `file_path` / `repository_path` and were rejected by the new path rule; the retries take the function name (2 call `git_log_lines`, 1 blames the function's lines). Each answer's evidence shows `155ac54`, checked by hand. The commit check did not need to fire |

| Summary | Round 5 | Round 7 |
| --- | --- | --- |
| Q1-Q7 correct or mostly correct | 4/7 | 5/7 (Q1 up from ⚠️ to 🟡; Q3, Q4, Q6 unchanged) |
| Q8 correct | 0/3 (round 6: 1/3) | **3/3** |
| Answers with valid citations | all | all 14 |
| Cited lines outside their evidence | not checked | 0 (now checked by code) |
| Invented paths in the final answer | Q1, every round | 0 (one caught and rewritten) |
| Invented runtime values | 0 | 0 |
| Time per question | 1-4 min (Q8 with tool creation 3-6 min) | 1.3-8.5 min; Q8 4-6 min, of which 3-3.5 min is tool creation |

**A bug the round exposed in the new path check:** Q1's first round-7 answer named real subfolders relative to their parent (`app/api/` "contains `dependencies/`, `errors/` and `routes/`"). The check only matched shortened names against files, so it reported six real folders as missing, cost one needless rewrite and showed a false "6 checks failed". Fixed in `ac5aaa2` (shortened names may match folders too; a wrong full path like `app/db/models/` still matches nothing), with a regression test. Re-checking every recorded answer from rounds 1-7, the check now flags only the three real `app/db/models/` inventions (rounds 1, 2 and 5). Q1 was then run once more (`results/round7/q1-after-fix/`).

### Unseen repositories (generality check, 2026-10-01)

Everything above uses one demo repository, so the same assistant was run on two repositories it had never seen, chosen to differ from the demo: a library with no web routes and a Flask web app. Ground truth was checked in their source and git history; assistant @ `94e0720`.

| Repository | Graph (built in ~2 s, 0 parse errors) | Question | Result |
| --- | --- | --- | --- |
| [pallets/itsdangerous](https://github.com/pallets/itsdangerous) @ `672971d` (library) | 15 modules, 106 functions, 0 routes, 61 doc sections; calls 36% resolved / 59% ambiguous / 5% unresolved | How does `TimedSerializer.loads` check that a token has not expired? | 🟡 Correct and every cited line accurate (`timed.py:204-220`): it calls `signer.unsign(..., max_age=...)` and re-raises `SignatureExpired`; did not follow the call to the age comparison itself (`timed.py:137-149`). 2 rounds, 108 s |
| [miguelgrinberg/microblog](https://github.com/miguelgrinberg/microblog) @ `a975ef6` (Flask app) | 34 modules, 119 functions, 27 routes; calls 72% / 6% / 22% | What happens when a user submits a new post on the index page? | ✅ Every step matches `app/main/routes.py:25-40` (validate form, detect language, create `Post`, add and commit, flash, redirect); omits `@login_required`, cites the file without line numbers. 3 rounds, 205 s |
| microblog | | When was the `follow` method in `app/models.py` last changed, and by whom? | ⚠️ Gap reported, tool created on the first attempt and used; reports the file's last change (Miguel Grinberg, 2017-11-01) and says it cannot tell when `follow` itself changed (truth: Miguel Grinberg, 2017-09-16). Honest, no invention. 2 rounds, 233 s |

**Found and fixed while doing this:** Flask blueprint prefixes were not applied, so microblog's `/api/...` and `/auth/...` routes appeared without them. The parser now handles `Blueprint(url_prefix=...)` and `app.register_blueprint(..., url_prefix=...)` as it already did FastAPI's routers (`94e0720`, with a test).

**What this shows:** ingestion, retrieval, citations and the tool pipeline work on unseen repositories with no changes; answer quality shows the same patterns as on the demo (correct and cited, sometimes stopping one call short; generated history tools working on the whole file instead of the function). Two unseen repositories is a smoke test, not a second evaluation.

## What the evaluation found, and what was fixed

**Round 1 → round 2 (`4c5d0a2`):**

1. **Context window (the biggest finding).** Ollama ran `gemma4:e4b` with a 4,096-token context and **silently dropped the start** of longer prompts, meaning the system prompt and the question. A 7,000-token test prompt was cut to 2,051 tokens with no error. Since phase 4 every multi-step question had been exposed to this. Fixed by setting `num_ctx` to 16,384; the Ollama log then showed `truncated = 0` on every call. This is the likely main cause of the round 1 → round 2 improvement on Q3, Q6 and Q7.
2. **`read_file` showed the model only 60 of the 200 lines it returned** (Q7 missed README line 74). Both are now 120 lines.
3. **Generated tools were always tested on invented names** (`some_function`), so every Q8 tool failed validation. The tool-writer prompt now lists real functions from the loaded repository, those the agent mentioned first.

**Round 2 → round 3 (`7cf9241`):**

4. **A generated tool fabricated data.** For Q4 the model reported a "count query" gap and wrote a tool that returns `{"count": 12345}` without reading anything. It passed the static check, ran in the container and returned a non-empty result, so it was registered; the agent then stated the number as fact with a *valid* citation, because E4 really was that tool's output. The citation check confirms that evidence exists, not that it is true (a documented limitation, here seen in practice). Fix: a generated tool whose test run makes **no `ctx` calls** is rejected, since its output cannot come from the repository; the prompt also forbids made-up or placeholder values. Regression test: `test_factory_rejects_tool_that_reads_nothing_from_ctx`.

## Remaining weaknesses (not fixed)

- **Generated tool logic varies:** in round 2, 2 of 3 Q8 tools used the file's last commit instead of blaming the function's lines, and got the wrong answer. Since round 7 that specific mistake is caught (commits that did not change the function are rejected) and `git_log_lines` makes the right approach one call; Q8 was correct 3/3. For other kinds of tools the pipeline still validates that a tool is safe, runs and reads repository data, not that it computes the right thing.
- **An invented folder name** in the structure answer (Q1, rounds 1-5). Since round 7 the answer check catches it and the one rewrite removes it; the model still writes it in its first draft.
- **Answers stop short:** Q3 did not follow the call into the repository. Since round 7 the graph does follow it (typed-call resolution), but in that run the model asked for callers instead of callees, so the answer did not improve. When the agent does use `query_graph` on calls, ambiguous calls are now listed under the answer by code (round 5); when it only reads the file, neither that list nor the diagram appears.
- **Runtime-only questions:** since round 3 no run invented a value (10 runs), but no run used the prescribed "cannot be known from the source code" framing; the model looks for a counting function instead. It also misread search hits as SQL it had found (rounds 3 and 5).
- **Tool use after creation:** in round 6, 2 of 3 created tools needed a file path and the agent passed a word from the question (`articles`) instead of looking the path up. Fixed in round 7: such tools are rejected at creation and rewritten to take the function name (3/3 first attempts rejected for this, 3/3 retries worked).
- **Prompt changes trade behaviours:** round 5's runtime rule stopped the git-history gap from being reported at all until round 6 separated the cases. Further prompt tuning was stopped for this reason.
- **Speed:** 1-5 minutes per question on this CPU, and the laptop occasionally slowed a single call to ~30 minutes when unattended.

## Generated tools

Every tool the model wrote during the evaluation is kept in [results/generated-tools/](results/generated-tools/), each with its `validation.json` (the gap, every attempt, the static-check and test-run results) and, when accepted, its `tool.py`:

| Folder | Round / question | Outcome |
| --- | --- | --- |
| `20260930-121853-failed`, `-122210-failed`, `-122545-failed` | Round 1, Q8 runs 1-3 | Rejected twice each: tested on invented names |
| `20260930-135726-count_table_records` | Round 2, Q4 | Accepted, **returns a hard-coded 12345** (would now be rejected: no ctx calls) |
| `20260930-141309-get_function_history` | Round 2, Q8 run 1 | Accepted; blames the function's lines; correct answer |
| `20260930-141559-get_function_history`, `-141846-get_function_history` | Round 2, Q8 runs 2-3 | Accepted; uses the file's last commit instead; wrong answer |
| `20260930-230941-git_history_for_symbol` | Round 6, Q8 run 1 | Accepted; file-level `git_log`; called with a non-existent path, refused |
| `20260930-231353-get_function_history` | Round 6, Q8 run 2 | Accepted; blames the function's lines, newest date wins; correct answer |
| `20260930-231924-get_function_git_history` | Round 6, Q8 run 3 | Accepted; file-level `git_log`; called with a non-existent path, refused |
| `20261008-153840-get_function_history` | Round 7, Q8 run 1 | Attempt 1 rejected (required `repository_path`); attempt 2 blames the function's lines; correct answer |
| `20261008-154420-get_function_git_history` | Round 7, Q8 run 2 | Attempt 1 rejected (required `file_path`); attempt 2 uses `git_log_lines`; correct answer |
| `20261008-154916-git_history_for_symbol` | Round 7, Q8 run 3 | Attempt 1 rejected (required `file_path`); attempt 2 uses `git_log_lines`; correct answer |

## Cases covered elsewhere

- **Validation failure with one retry** (plan case 11) is covered by unit tests rather than a live question: `test_factory_retries_once_with_errors` (unsafe code is rejected before it runs, the errors go back to the model, the second attempt passes) and `test_factory_gives_up_after_retry` (two failures leave the gap unresolved, with the audit record saved).
- **Container isolation** is tested against the real container: `test_container_has_no_network_and_readonly_fs` and `test_container_timeout_kills_the_tool` run code that deliberately bypasses the static check.
