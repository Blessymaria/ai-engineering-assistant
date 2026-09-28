# CLAUDE.md — AI Engineering Assistant

This file briefs Claude Code on this project. Read it at the start of every session.
The full approved plan is in `docs/PLAN.md`. If this file and the plan disagree, the plan wins; flag the conflict instead of guessing.

## What we are building

An assistant that answers questions about an unfamiliar **Python** repository: code structure, execution flows, dependencies, implementation behaviour and documentation. It builds its own code graph (GraphRAG), runs a custom agent loop with four core tools, detects capability gaps and generates new tools at runtime, and shows everything in a single-screen React UI with Markdown and Mermaid answers.

## Hard rules (never break these)

1. **No agent or LLM orchestration frameworks.** No LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex agents or similar. The agent loop is plain Python.
2. **No infrastructure outside the plan.** No Neo4j or other graph databases, no vector databases (Chroma, FAISS, Pinecone), no Redis, no microservices, no Kubernetes. If something seems necessary, stop and ask.
3. **Breeze is development-only.** Use the Breeze MCP server to understand *this* codebase while developing. The application must never call Breeze or use MCP at runtime.
4. **Never execute code from the analysed repository.** It is parsed with `ast` only.
5. **Generated tools only run inside a throwaway Docker container** (see Security). Never `exec`/`eval` generated code in the backend process.
6. **Exactly four core tools:** `search_code`, `query_graph`, `read_file`, `list_files`. Do not add more core tools; new capabilities come from the tool factory.
7. **Stay within the current phase.** Do not start work from a later phase without being asked.
8. **We have only 3 days.** Do not spend time on anything unnecessary: no polish, refactors, extra features, extra abstractions or "nice to have" work beyond the MVP. Choose the simplest thing that meets the requirement. See "Time budget".
9. **Log everything in `docs/DEVLOG.md`** (see "Documentation log").
10. **Never add Co-Authored-By, Claude-Session, 'Generated with Claude Code' or any other Claude/Anthropic attribution to commits, PRs, code comments, docs or the README.**

## Architecture decisions (fixed)

| Area | Decision |
| --- | --- |
| Backend | Python 3.13 + FastAPI; events streamed to the UI with Server-Sent Events |
| Frontend | React + TypeScript (Vite), react-markdown, Mermaid |
| Parsing | Python `ast`; Python repositories only |
| Graph | NetworkX, saved to a file; nodes: file/module, class, function/method, route, doc section; edges: CONTAINS, IMPORTS, INHERITS, HANDLES, MENTIONS, CALLS |
| Call resolution | Every CALLS edge has status `resolved`, `ambiguous` (candidates listed) or `unresolved`. Only `resolved` edges are confirmed paths. No type inference engine |
| Retrieval | Ranked lexical search (symbols, paths, docstrings, routes, source text, Markdown) + graph traversal + reading source. No embeddings in the MVP |
| Agent actions | Every LLM response is parsed into `ToolCall`, `CapabilityGap` (reserved `report_capability_gap` schema, never executed as a tool) or `FinalAnswer` |
| Loop | Sequential tool calls, max 12 tool rounds; at the limit, answer with what is known and state what is unresolved |
| Evidence | Full tool results stored backend-side as `E1`, `E2`, …; the LLM receives compact versions only |
| LLM | Local ~4B model via Ollama (Qwen3 4B or Gemma 4 E4B; Gemma 2B fallback), behind a small provider interface. Ollama runs natively on the host; the backend reaches it at `http://localhost:11434` |
| Citations | Answers cite evidence IDs and `file:line`; backend checks every cited ID exists (this does not prove semantic support) |

## Designing for a small local model

The model is small and runs on a laptop CPU, so keep its job small:

- Short tool descriptions and system prompt; compact tool results.
- Use Ollama's JSON-schema output mode for structured outputs (tool specs, gap reports).
- Generated tools use a **fixed template**: the model only writes the body of `run(args, ctx)`, guided by one complete example tool in the prompt.
- Expect slowness and occasional malformed output; handle errors gracefully instead of adding complexity.

## Dynamic tools and security

- Gap flow: agent returns `CapabilityGap` → system asks the LLM for a templated tool → static check → test run on the example input → output checked against the schema → one retry on failure → register for the session only → save code and validation result to disk.
- **Static check:** allowlisted imports only (`re`, `json`, `collections`, `itertools`, `math`); reject `eval`, `exec`, `compile`, `open`, `__import__`, `os`, `sys`, `subprocess`, network modules and any double-underscore names or attributes.
- **Execution:** `docker run --rm -i --network none --read-only` with 256 MB memory, 1 CPU and a 10-second timeout. The repository is not mounted and no secrets are passed.
- **ToolContext (`ctx`)** is the only route to data. Methods: `search_code`, `query_graph`, `read_file`, `list_files`, `list_nodes(kind)`, `git_log(path, limit)`, `git_blame(path, start, end)`. Communication is one JSON message per line over stdin/stdout. Only JSON crosses the boundary; never pass Python objects, the raw graph or backend objects.
- **Repository file access** must stay inside the loaded repo root: resolve canonical paths, reject paths and symlinks outside the root, skip `.git`, virtualenvs, `site-packages`, `node_modules`, `build`, `dist`, `__pycache__`, binaries and files over 1 MB; reject repositories over 5,000 files.
- Never commit secrets or `.env` files.

## Time budget: 3 days

The full plan was sized at roughly two weeks, so the reduced scope applies **from the start**: plain UI, 8 evaluation questions, and one demonstrated gap type (git history via `function_history`). Add the second gap type or more questions only if a day finishes early. All assignment requirements must still be met.

| Day | Goal by end of day |
| --- | --- |
| 1 | Phases 1–3: repo, skeletons, model chosen (one-hour test), graph built for the demo repo, four core tools working with tests |
| 2 | Phases 4–5: agent loop answering multi-step questions from the command line; one capability gap producing a validated tool that runs in Docker |
| 3 | Phases 6–7: single-screen UI with Markdown, Mermaid and activity panel; 8-question evaluation; README with setup, assumptions and limitations |

Rules for staying on time:

- Unit tests only for core logic (path safety, graph building, call resolution, tools, static checks, ctx protocol). No test suites for UI styling.
- If a task takes much longer than expected, stop, write down the blocker in `docs/DEVLOG.md`, and propose the simplest workaround instead of pushing on.
- Prefer a working end-to-end path over completeness in any single part.

## Documentation log (`docs/DEVLOG.md`)

Keep a running record of the work in `docs/DEVLOG.md`, separate from the README. Update it at every commit-worthy step. Each entry is short:

```
## <date> <time> — <phase>: <what was done>
- Changes: <files/modules touched>
- Decisions: <any choice made and why, especially deviations from docs/PLAN.md>
- Verified: <tests run / commands and results>
- Issues / next: <open problems, what comes next>
```

This log is used to write the README and to explain the work to reviewers, so record decisions and deviations honestly, including things that did not work.

## Phases (build in this order)

1. **Setup:** repo skeleton, backend and frontend apps start locally, README stub, Breeze indexing, Docker and Ollama installed, one-hour model selection test.
2. **Code graph:** load repo with path/size limits, parse with `ast`, build and save graph with call status.
3. **Core tools:** the four tools with unit tests, correct on the demo repo.
4. **Agent loop:** structured actions, evidence store, step limit, event streaming; multi-step questions work from the command line.
5. **Dynamic tools:** gap handling, templated generation, static checks, Docker runner with JSON `ctx`, test run, registration, audit files.
6. **UI:** repository bar, chat with Markdown/Mermaid (show source if a diagram fails), activity panel.
7. **Evaluation and README:** 8-question set, results, setup, assumptions and limitations in the README.

Given the 3-day budget, the reduced scope in "Time budget" already applies. Never cut an assignment requirement to save time; cut polish instead.

Demo repository: `fastapi-realworld-example-app` (confirm in phase 2).

## How to work

- **Start each phase in plan mode**: summarise what you will build and which files you will touch, and wait for approval.
- Work in small steps. After each working step, run the relevant tests, then commit with a clear message (e.g. `feat(graph): add CALLS resolution status`). Keep history readable; it is part of the assessment.
- Write tests alongside code (`pytest` for backend). Do not mark a step done if its tests fail.
- Prefer simple, readable code over clever abstractions. Add a dependency only when it removes real work, and say why in the commit message.
- Ask before running anything destructive (`rm -rf`, `git push --force`, deleting branches) or pushing to the remote.
- When unsure whether something is in scope, check `docs/PLAN.md`, then ask.
- At meaningful milestones, remind the user to refresh the Breeze ontology.

## Proposed layout (adjust if the plan requires)

```
backend/
  app/
    api/          # FastAPI routes, SSE
    ingest/       # cloning, path safety, ast parsing, graph build
    graph/        # graph storage and queries
    tools/        # the four core tools
    agent/        # loop, actions, evidence store, prompts
    llm/          # provider interface + Ollama provider
    toolfactory/  # gap handling, generation, static checks, registry
    runner/       # Docker runner and ctx protocol
  tests/
runner-image/     # Dockerfile + ctx stub for generated tools
frontend/
docs/
  PLAN.md
  DEVLOG.md       # running log of work, decisions and results
eval/             # evaluation questions and results
```

## Environment notes

- Development machine: Windows 11, 32 GB RAM, Intel CPU, no dedicated GPU. Ollama runs natively; Docker Desktop provides containers.
- Use paths and commands that work on Windows (PowerShell or Git Bash); avoid Linux-only assumptions in scripts.

## Commands

Fill these in during phase 1 and keep them current.

- Backend: `TODO`
- Frontend: `TODO`
- Tests: `TODO`
- Build runner image: `TODO`
