# Evaluation results

Eight questions on [fastapi-realworld-example-app](https://github.com/nsidnev/fastapi-realworld-example-app), each with its expected facts written from the source and git history **before** any run ([questions.json](questions.json), committed in `d85885e`). Every answer was checked by hand against those facts and against the cited source lines. Full transcripts, every step and all evidence are in [results/](results/).

## Context

| | |
| --- | --- |
| Model | `gemma4:e4b` via Ollama 0.34.4, temperature 0 |
| Hardware | Intel Core Ultra 5 225U, 32 GB RAM, CPU only (no GPU), Windows 11 |
| Demo repository | `fastapi-realworld-example-app` @ `029eb7781c60d5f563ee8990a0cbfb79b244538c` (full history, 209 commits) |
| Round 1 | assistant @ `d85885e`, run 2026-09-30 11:56 |
| Round 2 | assistant @ `4c5d0a2` (three fixes found by round 1), run 2026-09-30 12:42 (resumed at 13:20 after a stalled model call) |
| Round 3 | assistant @ `7cf9241` (fix found by round 2), Q4 only, run 2026-09-30 14:20 |

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

## What the evaluation found, and what was fixed

**Round 1 → round 2 (`4c5d0a2`):**

1. **Context window (the biggest finding).** Ollama ran `gemma4:e4b` with a 4,096-token context and **silently dropped the start** of longer prompts, meaning the system prompt and the question. A 7,000-token test prompt was cut to 2,051 tokens with no error. Since phase 4 every multi-step question had been exposed to this. Fixed by setting `num_ctx` to 16,384; the Ollama log then showed `truncated = 0` on every call. This is the likely main cause of the round 1 → round 2 improvement on Q3, Q6 and Q7.
2. **`read_file` showed the model only 60 of the 200 lines it returned** (Q7 missed README line 74). Both are now 120 lines.
3. **Generated tools were always tested on invented names** (`some_function`), so every Q8 tool failed validation. The tool-writer prompt now lists real functions from the loaded repository, those the agent mentioned first.

**Round 2 → round 3 (`7cf9241`):**

4. **A generated tool fabricated data.** For Q4 the model reported a "count query" gap and wrote a tool that returns `{"count": 12345}` without reading anything. It passed the static check, ran in the container and returned a non-empty result, so it was registered; the agent then stated the number as fact with a *valid* citation, because E4 really was that tool's output. The citation check confirms that evidence exists, not that it is true (a documented limitation, here seen in practice). Fix: a generated tool whose test run makes **no `ctx` calls** is rejected, since its output cannot come from the repository; the prompt also forbids made-up or placeholder values. Regression test: `test_factory_rejects_tool_that_reads_nothing_from_ctx`.

## Remaining weaknesses (not fixed)

- **Generated tool logic varies:** in round 2, 2 of 3 Q8 tools used the file's last commit instead of blaming the function's lines, and got the wrong answer, even though `git_blame` and the function's line range were available. The pipeline validates that a tool is safe, runs, and reads repository data; it cannot validate that the tool computes the right thing.
- **No citations for overview questions** (Q1 in both rounds) and an invented folder name, although the prompt requires citations.
- **Answers stop short:** Q3 did not follow the call into the repository, and did not flag that call as unconfirmed although the graph marks it ambiguous. The Mermaid diagram is only drawn when the agent used `query_graph` on calls (Q5, Q6 in round 2; not Q3).
- **Runtime-only questions:** the agent never explained, in any round, that stored data cannot be known from static analysis; round 3 also misreported search hits as SQL it had found. The model takes different paths on the same question (round 2 reported a gap and built a tool, round 3 did not).
- **Speed:** 1-5 minutes per question on this CPU, and the laptop occasionally slowed a single call to ~30 minutes when unattended.

## Cases covered elsewhere

- **Validation failure with one retry** (plan case 11) is covered by unit tests rather than a live question: `test_factory_retries_once_with_errors` (unsafe code is rejected before it runs, the errors go back to the model, the second attempt passes) and `test_factory_gives_up_after_retry` (two failures leave the gap unresolved, with the audit record saved).
- **Container isolation** is tested against the real container: `test_container_has_no_network_and_readonly_fs` and `test_container_timeout_kills_the_tool` run code that deliberately bypasses the static check.
