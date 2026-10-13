---
name: phase-3-core-tools
description: Phase 3 of the AI Engineering Assistant - the four core tools (search_code, query_graph, read_file, list_files), their schemas and validation. Use when changing or debugging a core tool, its result format, or the tool registry (backend/app/tools).
---

# Phase 3: the four core tools

`CLAUDE.md` and `docs/PLAN.md` are the source of truth.

## Rules

- **Exactly four core tools:** `search_code`, `query_graph`, `read_file`, `list_files`. Never add a fifth; new
  capabilities come from the tool factory (phase 5).
- Every read goes through the phase 2 path-safety rules (`LoadedRepo.text`).
- Keep results compact for a small model: short descriptions, bounded result counts.

## Behaviour

| Tool | Contract |
| --- | --- |
| `search_code` | Weighted lexical scoring, no embeddings: exact symbol or route match first, then name, path and docstring words, then source and doc lines (at most 3 per file, labelled with their enclosing function) |
| `query_graph` | Relations: callers, callees, imports, imported_by, contains, inherits, subclasses, handlers, mentions. Depth up to 3, up to 60 results. Only resolved calls are expanded; ambiguous and unresolved calls are listed with a note to read the source |
| `read_file` | Numbered lines, 120-line window (matching what the agent shows the model, so nothing returned is hidden) |
| `list_files` | Tree with file counts for folders cut off by depth |

- `registry.py` holds one JSON schema and one-line description per tool, plus an argument validator with clear errors.
  Accept numeric strings such as `"10"`: small models send them.
- Unknown node names return an error that tells the model to use `search_code` to find the right id; the agent
  recovers from it (seen in the round-7 flow run).

## Lessons

- Route ids end with their handler id, so a short handler name also matched the route; match routes by name only.
- A window shorter than what the model is shown hid answers (README line 74 in round 1); keep the two limits equal.

## Done when

`test_tools.py` covers the change, including a check on the demo repository (skipped when it is not cloned), and the
CLI still works: `.venv/Scripts/python -m app.tools search_code '{"query": "POST /articles"}'`.
