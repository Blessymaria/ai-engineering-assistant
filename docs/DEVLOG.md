# Development log

## 2026-09-28 — Setup: add project brief, technical plan and devlog
- Changes: `CLAUDE.md`, `docs/PLAN.md`, `docs/DEVLOG.md`, `.gitignore`
- Decisions: added a hard rule against Claude/Anthropic attribution (`.claude/settings.local.json` is git-ignored). Plan and devlog live in `docs/` to match the proposed layout; added `node_modules/` and `workspace/` (cloned repositories) to `.gitignore`; `.env` and `.venv` were already ignored by the Python template.
- Verified: `git status` shows only the intended files; no secrets committed.
- Issues / next: start phase 1 (setup) in plan mode.

## 2026-09-28 — Setup: resolve brief inconsistencies
- Changes: `CLAUDE.md`
- Decisions: Python 3.13 instead of 3.12 (already installed; FastAPI supports it; deviation from the brief, approved). Model selection test is one hour (brief said 30 minutes in one place; `docs/PLAN.md` wins). Phase 7 uses 8 evaluation questions to match the reduced 3-day scope.
- Verified: n/a (docs only).
- Issues / next: backend skeleton; Node.js, Docker Desktop and Ollama still need installing.

## 2026-09-28 — Setup: backend skeleton and README stub
- Changes: `backend/` (FastAPI app with `/api/health`, empty packages from the proposed layout, pytest config, pinned requirements), `README.md`, `CLAUDE.md` (Commands)
- Decisions: API routes live under `/api` so the Vite dev server can proxy them (no CORS setup). Runtime deps in `requirements.txt`, test deps in `requirements-dev.txt`. Test client uses `httpx2` because Starlette deprecates `httpx` for `TestClient`.
- Verified: `pytest` 1 passed, no warnings; `uvicorn` started and `GET /api/health` returned `{"status":"ok"}`.
- Issues / next: frontend skeleton needs Node.js; model test needs Ollama; Docker Desktop still to install.

## 2026-09-28 — Setup: frontend skeleton
- Changes: `frontend/` (Vite React + TypeScript template, trimmed to one page that shows backend health), `vite.config.ts` (proxy `/api` to port 8000), `README.md`, `CLAUDE.md` (Commands)
- Decisions: kept the template's oxlint linter instead of adding ESLint. Removed template demo assets. Node.js 24 LTS was installed by IT (account has no local admin rights).
- Verified: `npm run build` and `npm run lint` clean; with both apps running, `GET http://localhost:5173/api/health` through the proxy returned `{"status":"ok"}` and the page served.
- Issues / next: one-hour model test (qwen3:4b 2.5 GB and gemma4:e4b 9.6 GB pulled). Docker Desktop and WSL still pending with IT.

## 2026-09-28 — Phase 2: repository loading and path safety
- Changes: `backend/app/ingest/paths.py`, `backend/app/ingest/loader.py`, `backend/tests/test_paths.py`
- Decisions: all file-access rules (root containment, skipped dirs, virtualenv detection via `pyvenv.cfg`, 1 MB / binary / 5,000-file limits) live in `paths.py` so `read_file` can reuse them in phase 3. Clones are shallow (`--depth 1`) into `workspace/`; only `http(s)://` and `git@` URLs are accepted, which also blocks option injection such as `--upload-pack`.
- Verified: `pytest` 15 passed, 1 skipped (symlink test needs Windows symlink rights).
- Issues / next: parsing and graph building.

## 2026-09-28 — Phase 2: code graph with call resolution
- Changes: `backend/app/ingest/{parser,calls,docs}.py`, `backend/app/graph/{build,store}.py`, `backend/tests/test_graph.py`, `backend/tests/fixtures/shop/`, `networkx` added to requirements.
- Decisions:
  - Node ids are dotted qualified names (`app.services.articles.create_article`); routes are `route:<METHOD> <path> -> <handler>`, doc sections `doc:<file>#L<line>`.
  - Library targets become `external` nodes (`ext:json.dumps`) and count as resolved calls; calls with no target become `unresolved:<name>` placeholder nodes, so every CALLS edge has a real target and a status.
  - A single name-only match (e.g. `repo.get()` with one `get` method in the repo) is still `ambiguous`: it is not found via imports, so it is not confirmed.
  - Builtins and method calls on local values with no matching repo method (`items.append()`) are not recorded, to keep the graph small for the model.
  - Re-exports through `__init__.py` are followed (up to 5 hops).
  - Added reStructuredText headings: the demo repository's only doc is `README.rst`. Small deviation from "README/Markdown" in the plan.
  - Route paths include FastAPI `APIRouter(prefix=...)` and `include_router(prefix=...)` chains. Non-constant prefixes (the demo's `/api` from `settings.api_prefix`) cannot be known statically and are left out (limitation for the README).
  - Demo repository confirmed: `fastapi-realworld-example-app` @ `029eb77`.
- Verified: `pytest` 39 passed, 1 skipped. Demo graph built in ~5 s: 95 modules, 59 classes, 185 functions, 20 routes (all with full paths), 6 doc sections, 0 parse errors; CALLS 414 = 66% resolved, 25% ambiguous, 9% unresolved. Spot check: `POST /articles` → `create_new_article`, which calls `ArticlesRepository.create_article` as ambiguous (injected via `Depends`).
- Issues / next: methods inherited from library classes (e.g. pydantic `from_orm`) show as unresolved; acceptable for now. Next: phase 3, the four core tools.

## 2026-09-29 — Setup: model selection test
- Changes: `eval/model_test.py`, `eval/results/model_test.json`, `CLAUDE.md` (LLM row)
- Decisions: **`gemma4:e4b` chosen** (approved). Test: 8 single tool-call cases through Ollama native tool calling (6 core-tool choices, 2 capability gaps) + 2 tool-spec generations in JSON-schema mode, temperature 0, replies capped (256 tokens for tool calls, 1024 for specs).

  | Model | Tool calls | Tool specs | Avg response | Speed |
  | --- | --- | --- | --- | --- |
  | qwen3:4b (2.5 GB) | 0/8 | 2/2 | 49 s | 6.8 tok/s |
  | gemma4:e4b (9.6 GB) | 6/8 | 0/2 | 39 s | 6.7 tok/s |

  - qwen3:4b was inconsistent: the first run made all 8 tool calls correctly, but later runs wrote long reasoning into the reply despite `think: false` and `/no_think`, and never called a tool within the cap (one earlier call ran for 27 minutes with no cap).
  - gemma4:e4b made all 6 core-tool calls correctly with short replies (17-33 tokens, ~25 s). For the 2 gap questions it called `search_code` first instead of reporting a gap; acceptable, since the agent reports gaps after tools fall short, and the system prompt can steer this.
  - gemma4:e4b's tool specs were too long (hit the 1024-token cap, so the JSON was incomplete) and used a made-up `ctx` method. Phase 5 needs a stricter prompt: only the real `ctx` methods, short code, the fixed template.
  - The spec check first required a `def run(args, ctx)` line although the prompt asks for the body only; fixed to wrap body-only code before the syntax check (after these results were recorded).
- Verified: full run completed; results in `eval/results/model_test.json`.
- Issues / next: ~25-40 s per model step on this CPU, so one agent question takes minutes; keep tool rounds and prompts small in phase 4. Always cap reply length (`num_predict`).

## 2026-09-29 — Phase 3: four core tools
- Changes: `backend/app/tools/{repo,search,graph_query,files,registry,__main__}.py`, `backend/tests/test_tools.py`, `CLAUDE.md` (Commands)
- Decisions:
  - `LoadedRepo` holds the root, graph and cached file text; all reads go through the phase 2 path-safety rules.
  - `search_code`: weighted lexical scoring, no embeddings. Exact symbol/route matches score 100; then query words found in the name (+20 if all), the id/path and the docstring; then source/doc lines containing all query words or the exact phrase (max 3 per file, labelled with their enclosing function). Words are split on snake_case/CamelCase/acronyms and lightly stemmed (`articles` = `article`). Lock files are skipped as noise.
  - `query_graph`: relations callers, callees, imports, imported_by, contains, inherits, subclasses, handlers, mentions (the last two work in both directions). Depth ≤ 3, ≤ 60 results. Only resolved calls are followed to the next level; ambiguous/unresolved calls are listed with a note to read the source. Nodes can be given by id, unique dotted suffix, name, or route (`POST /articles`); several matches return the candidate ids instead of a guess.
  - `read_file`: numbered lines, ≤ 200 per call, with total line count. `list_files`: tree with file counts for folders cut off by depth, ≤ 200 entries.
  - `registry.py`: one JSON schema + one-line description per tool, and a small argument validator (clear error messages; numeric strings such as `"10"` accepted because small models send them).
  - `subclasses` and `imported_by` are extra relations beyond the plan's list; they are reverse directions of existing edges and needed for dependency/structure questions.
- Verified: `pytest` 79 passed, 1 skipped (symlink). Demo checks: `POST /articles` is the top search hit and leads to `create_new_article`; its callees (depth 2) show services as resolved, `ArticlesRepository.create_article` as ambiguous, `from_orm` as unresolved, and stop at unconfirmed calls; "article repository" finds `ArticlesRepository` first.
- Issues / next: tests first failed because route ids end with their handler id, so a short handler name matched the route too; fixed by matching routes by name only. The auto-mode command check was unavailable for long stretches; allow rules for pytest/app CLIs/git (not push) were added to local settings. Next: phase 4, the agent loop.

## 2026-09-29 — Setup: Breeze indexing (development only)
- Changes: `.repoignore` (excludes `workspace/`, `.venv/`, `node_modules/`, `.breeze.json`), `.gitignore` (`.cog/`). Outside the repo: Breeze project `ai-engineering-assistant` (`94a3bca5-…`), `.breeze.json` and `breeze-onboard.sh` in the parent folder (the API key never enters the repo).
- Decisions: the Breeze indexer (`breezeai-cog` via `uvx`) cannot build natively on Windows: its Groovy tree-sitter dependency needs the MSVC build tools (admin). `wsl --install` failed on the corporate network (certificate error fetching the distro list), so Ubuntu 24.04 was downloaded from cloud-images.ubuntu.com and added with `wsl --import` (no admin). Inside it: `uv` and `build-essential`. Automatic upload with an API key.
- Verified: indexer parsed 38 files, 69 functions, 15 classes; `Code_Graph_Search` in Breeze finds `backend/app/tools/search.py::search_code` (code ontology 2848).
- Issues / next: the 3 TypeScript files were skipped: the TS parser downloads from GitHub inside WSL and fails the corporate certificate check (`UnknownIssuer`). The backend (the bulk of the code) is indexed; frontend indexing can wait for phase 6. The upload's status poll returns HTTP 400 "projectUuid query param is required" although the upload lands (Breeze-side bug; same error from the repository-list MCP tool). Re-index at milestones with `wsl -d Ubuntu -u root -- bash "/mnt/c/Users/BlessyMariaMathew/Desktop/Project 1/breeze-onboard.sh"`.

## 2026-09-29 — Phase 4: agent loop
- Changes: `backend/app/llm/{base,ollama}.py`, `backend/app/agent/{actions,evidence,loop,prompts,__main__}.py`, `backend/app/api/routes.py` (`POST /api/ask`, SSE), `backend/app/main.py`, `backend/app/graph/store.py` (`latest_graph`), `backend/tests/test_agent.py`
- Decisions:
  - Provider interface + Ollama provider (stdlib HTTP, no new dependency); every call sets temperature 0, `think: false` and `num_predict` 1024.
  - Each reply is parsed into exactly one action: ToolCall, CapabilityGap (reserved `report_capability_gap` schema, never executed), FinalAnswer or Invalid. Only the first of several tool calls runs; tool calls written as JSON text are accepted.
  - Evidence store keeps full results (`E1`, `E2`, …); the model sees compact text, and results older than the last 3 shrink to a one-line summary. Graph results state both "defined at" and "call at file:line".
  - 12 tool rounds, then a forced answer with no tools. Tool errors and invalid actions go back to the model and count toward the limit. An answer with no evidence and no reported gap is sent back once ("look at the code first").
  - Phase 4 gap handling: the gap is recorded and the model is told no tool can be created yet (phase 5 replaces this).
  - Citation check validates that cited `E<n>` ids exist (not that they support the claim).
- Verified: `pytest` 98 passed, 1 skipped (loop tested with a scripted fake model). Real runs with gemma4:e4b on the demo repo, checked by hand against the source:

  | Question | Rounds | Time | Citations | Result |
  | --- | --- | --- | --- | --- |
  | What happens when POST /articles is called? (first prompt) | 7 | 349 s | 5/5 | Correct route → repository → SQL flow, cited lines 44/45/55/56/58 verified; skipped the two service calls, no Mermaid, did not flag the ambiguous repo call |
  | Same question (revised prompt) | 5 | 216 s | 4/4 | Every step in order incl. services and the 400 check; ambiguous repo call flagged; still no Mermaid |
  | Which modules depend on app.db.repositories.articles? (first) | 5 | 182 s | 2/2 | Incomplete: 2 of 6 importers |
  | Same (revised prompt) | 6 | 349 s | 3/3 | 3 of 6 importers (misses `app.api.dependencies.articles` and 2 test modules); vague hedging on one module |
  | Where is the JWT token created, and who uses it? (first) | 4 | 192 s | 3/3 | Creation correct (`jwt.py:15/27/28`); call-site lines wrong (cited caller definitions, e.g. `authentication.py:23` for a call at line 41); missed token decoding in `dependencies/authentication.py:84` |

- Issues / next:
  - Almost all time is the model (7-35 s per tool step, 95-180 s for the final written answer on CPU); tools take < 0.3 s.
  - The wrong call-site lines came from the compact format (function start line shown first); fixed by printing "defined at … ; call at …". Not yet re-verified on the JWT question.
  - gemma4:e4b does not produce Mermaid despite the prompt, and does not always list every item a tool returned. Options for phase 6/7: build the Mermaid diagram in code from the visited graph nodes instead of asking the model; keep prompts short.
  - Next: phase 5, dynamic tool creation (git history gap) and the container runner.

## 2026-09-29 — Phase 5: dynamic tools in a locked-down container
- Changes: `backend/app/runner/{docker,context}.py`, `backend/app/toolfactory/{static_check,factory}.py`, `backend/app/agent/{loop,prompts,__main__}.py`, `backend/app/api/routes.py`, `backend/app/llm/*` (`json_schema` option), `backend/app/ingest/loader.py` (full-history clones), `runner-image/`, `.gitattributes` (`*.sh` stay LF), `CLAUDE.md`, `backend/tests/test_toolfactory.py`
- Decisions:
  - **Containers without Docker Desktop:** Docker Engine installed with apt inside the WSL `Ubuntu` distro (no admin rights, no IT). Docker Hub is unreachable here (TLS handshake timeout), so the runner image `aiea-python-base:local` (Ubuntu 24.04 + Python 3.12, 277 MB) is built locally with debootstrap from the Ubuntu mirror (`runner-image/build-local.sh`); a Dockerfile is kept for machines with Hub access. The backend calls `wsl -d Ubuntu -u root -- docker` on Windows (`AIEA_DOCKER` overrides). Hard rule 5 is unchanged.
  - Each run: `docker run --rm -i --network none --read-only --memory 256m --cpus 1 --pids-limit 64 --cap-drop ALL --security-opt no-new-privileges`, unique name, 10 s timer that `docker kill`s the container. Nothing is mounted; no secrets. The tool code and args go in as the first JSON line on stdin; a harness inside the container runs it (the backend never executes generated code). ~0.5 s container start-up via wsl.exe.
  - ToolContext serves only: the four core tools (same validation), `list_nodes(kind)`, read-only `git_log(path, limit)` and `git_blame(path, start, end)` (paths confined to the repo root and required to exist).
  - Factory: LLM fills the body of a fixed `run(args, ctx)` template, guided by one example tool and the real ctx method list, in JSON-schema mode (max 1500 tokens). Checks: name, input-schema normalisation (small models write `{"symbol": "string"}` shorthand), example input matches schema, static check (allowlisted imports; no eval/exec/compile/open/getattr/os/sys/subprocess/network modules; no dunder names), test run in the container, result must be a non-empty dict without an `error` key. One retry with the errors. Registered for the session only; `tool.py` + `validation.json` (every attempt) saved under `workspace/tools/`. At most 2 tools created per question.
  - Clones now keep full history (the demo was shallow; `git fetch --unshallow`, 209 commits), otherwise git tools have nothing to report.
- Verified: `pytest` 131 passed, 1 skipped. The Docker tests run against the real container: ctx round trip, code that deliberately bypasses the static check still gets "Network is unreachable" and "Read-only file system", an infinite loop is killed by the timeout. Real runs with gemma4:e4b, "When was the create_article function in the articles repository last changed, and by whom?" (truth from git: Nik, 2020-05-01, #35):

  | Run | Tool created | Attempts / time | Answer | Verdict |
  | --- | --- | --- | --- | --- |
  | 1 | `get_git_history(path)` | 1 / 41 s | "history empty, cannot determine" | Honest but no answer: tool tested on a non-existent `src/main.py` (git log silently returned nothing), agent called it with `path='articles'` |
  | 2 (after fixes below) | `get_function_git_info(target_name)` via `list_nodes` + `git_blame` of the function's lines | 1 / 88 s | Nik, 2019-11-18 | Author right, date wrong: returned the blame of the first line only |
  | 3 (after blame doc fix) | `get_git_history_for_node(node_name, node_kind, file_path)` | 2 / 237 s | Nik, 2020-05-01 | Correct, but the tool blamed the whole file (46 KB result, model saw the first 3.5 KB); partly luck |

  Fixes between runs: git helpers reject non-existent paths; a test result with an `error` key is a failure; the prompt asks to take the agent's kind of input (a function name), find its lines via ctx, not to catch exceptions, and documents that `git_blame` returns one entry per line in line order.
- Issues / next:
  - The pipeline itself works every time (gap -> generated -> static check -> container test -> registered -> used), but gemma4:e4b's tool logic varies run to run. Test runs still pass on made-up example inputs when the tool returns a "not found" status instead of an error (`some_function_name`). Possible later improvement: run the test on the agent's own example input.
  - Tool creation takes 40-240 s on CPU; a question with a gap takes 2-6 minutes.
  - Breeze re-index at this milestone built fine (51 files, 128 functions, 37 classes) but the upload returned HTTP 409 "Duplicate entry": the indexer cannot replace an existing repository. The old one must be deleted in the Breeze UI (code-ontology page) before each re-upload.
  - Next: phase 6, the UI.

## 2026-09-30 — Phase 6: single-screen UI
- Changes: `backend/app/api/routes.py` (`GET/POST /api/repo`, error safety in the stream), `backend/app/agent/diagram.py`, `backend/app/agent/{loop,prompts}.py`, `backend/tests/test_ui_api.py`; `frontend/src/{App,api,events,types}.ts(x)`, `frontend/src/components/{RepoBar,Chat,Activity,Detail,Markdown,Mermaid}.tsx`, `frontend/src/index.css`; packages `react-markdown`, `remark-gfm`, `mermaid`.
- Decisions:
  - **Mermaid diagrams are built in code** from the query_graph evidence the agent visited (solid = resolved, dashed = ambiguous/unresolved, library calls left out), instead of asking the model: gemma4:e4b never produced one in phase 4, and this guarantees only visited nodes appear (plan section 7). Model-written Mermaid blocks still render. The prompt no longer asks for diagrams, which also shortens the slowest step (the final answer).
  - The browser parses the SSE stream from `POST /api/ask` itself (EventSource only supports GET). Events are folded into activity steps by a pure reducer (`events.ts`); model time is attached to the step it produced.
  - Citations `[E3, file:line]` become links that open the full evidence; steps open their full result, or a created tool's code and test run. The activity panel shows actions only, no model reasoning.
  - `POST /api/repo` builds the graph synchronously (~5 s for the demo) with a spinner, rather than progress events.
  - Each question is independent (no conversation memory), matching the plan's one-question-at-a-time loop.
  - Plain CSS; no UI framework. The Mermaid bundle is large (build warns about >500 kB chunks); acceptable for a local app.
- Verified: `pytest` 138 passed, 1 skipped; `npm run build` and `npm run lint` clean. Through the Vite dev server: page and `/api/repo` load; a real question streamed through the proxy with events arriving live (+48 s, +70 s, +78 s, answer at +122 s), 3/3 citations valid.
- Issues / next:
  - In that run the model queried `callers` of `login` when asked what it calls, so the answer missed the calls and no diagram was drawn (nothing to draw). Model weakness to record in the evaluation.
  - `npm audit` reports `lodash-es` (via mermaid) advisories for `_.template`/`_.unset`, which this app never calls with untrusted input; the offered fix is a breaking forced downgrade, so not applied.
  - Next: phase 7, evaluation (8 questions) and README.
- Follow-up fixes after first browser use: blank page in Edge (an effect returned `scrollIntoView`'s Promise, `61378d9`); the repository box was mistaken for the question box, now labelled (`7eaff3c`).

## 2026-09-30 — Phase 7: evaluation and README
- Changes: `eval/questions.json`, `eval/run_eval.py`, `eval/results/round{1,2,3}/`, `eval/RESULTS.md`, `README.md`; fixes in `backend/app/llm/ollama.py`, `backend/app/agent/evidence.py`, `backend/app/tools/{files,registry}.py`, `backend/app/toolfactory/factory.py` and tests.
- Decisions:
  - Question set (approved, with two swaps from the first draft): structure, nonexistent symbol, flow, runtime-only data, dependencies, implementation, documentation, git-history gap (run 3 times). Expected facts written from source and git and committed before any run (`d85885e`). The validation-failure case is covered by unit tests instead of a question.
  - Each round is committed as it ran before any fix (`ad73a2d`, `5dfbb7b`); fixes only for bugs the evaluation exposed; nothing tuned to question wording.
- Verified (full detail in `eval/RESULTS.md`): Q1-Q7 correct or mostly correct 2/7 in round 1, 5/7 in round 2; citation references valid 8/8 and 12/12, cited lines checked by hand; Q8 tools created 0/3 then 3/3, correct answer 0/3 then 1/3. `pytest` 141 passed, 1 skipped.
- Bugs found by the evaluation and fixed:
  1. **Ollama ran the model with a 4,096-token context and silently dropped the start of longer prompts** (system prompt and question); a 7,000-token probe was cut to 2,051 tokens. Now `num_ctx` 16,384; the server log shows `truncated = 0`. This affected every multi-step question since phase 4.
  2. `read_file` returned 200 lines but the model saw 60 (Q7 missed README line 74); both are now 120.
  3. Generated tools were tested on invented names (`some_function`) and always rejected; the tool-writer prompt now lists real functions from the loaded repository.
  4. **A generated tool returned a hard-coded `count: 12345`** for "how many articles are stored?", passed every check, and the agent stated it as fact with a valid citation. Tools whose test run makes no `ctx` calls are now rejected (`7cf9241`). In round 3 the model took a different path (no gap), so the check was not exercised live; it is covered by `test_factory_rejects_tool_that_reads_nothing_from_ctx`.
- Issues / next:
  - Not fixed: generated tool logic varies (2/3 git-history tools used the file's last commit instead of the function's lines); no citations on overview questions; flow answers stop short; runtime-only questions never get the "cannot be known statically" explanation.
  - Twice a single model call stalled for ~30 minutes while the laptop was unattended (power saving); the runner now records a failed question and continues.
