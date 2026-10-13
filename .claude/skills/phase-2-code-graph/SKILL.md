---
name: phase-2-code-graph
description: Phase 2 of the AI Engineering Assistant - loading repositories safely and building the NetworkX code graph with ast, including call resolution statuses, routes and doc sections. Use when changing ingestion, path safety, parsing, call resolution or graph building (backend/app/ingest, backend/app/graph).
---

# Phase 2: repository loading and the code graph

`CLAUDE.md` and `docs/PLAN.md` are the source of truth.

## Rules

- **Never execute code from the analysed repository.** Parse with `ast` only.
- File access stays inside the repository root: canonical paths, no symlinks out, skip `.git`, virtualenvs
  (`pyvenv.cfg`), `site-packages`, `node_modules`, `build`, `dist`, `__pycache__`, binaries and files over 1 MB;
  reject repositories over 5,000 files. All rules live in `ingest/paths.py` so every tool reuses them.
- Only `http(s)://` and `git@` URLs are cloned; local folders only under `AIEA_ALLOWED_ROOTS`.
- Graph: NetworkX, saved as node-link JSON per repository and commit. Nodes: module, class, function, route, doc
  section. Edges: CONTAINS, IMPORTS, INHERITS, HANDLES, MENTIONS, CALLS. No graph database.
- Every CALLS edge is **resolved** (one target via imports, same-module definitions, `self`/`cls`), **ambiguous**
  (name-matched candidates) or **unresolved**. Only resolved edges are confirmed paths. No type-inference engine.

## Decisions to keep

- Node ids are dotted qualified names; routes `route:<METHOD> <path> -> <handler>`; docs `doc:<file>#L<line>`.
- Library targets are `external` nodes; calls with no target get `unresolved:<name>` nodes, so every edge has a
  target and a status. A single name-only match is still ambiguous.
- Types written in the code may be used, not inferred: a call on a parameter annotated with a repository class, or on
  `self.x` assigned from a class in `__init__`, resolves to that class's method, and stays ambiguous if a subclass
  overrides it (cut the demo's ambiguous calls from 103 to 76).
- Routes include FastAPI router prefixes and Flask blueprint prefixes; prefixes from runtime settings cannot be seen.
- Clones keep full history: the generated git tools need every commit.

## After changing graph building

Saved graphs in `workspace/graphs/` keep the old behaviour until rebuilt: rebuild them, compare resolved / ambiguous /
unresolved counts before and after, and say what changed per repository.

## Done when

Tests in `test_graph.py` and `test_paths.py` cover the change (with a small fixture that includes the cases that must
stay unconfirmed), the demo graph builds with 0 parse errors, and a spot check on `POST /articles` is correct.
