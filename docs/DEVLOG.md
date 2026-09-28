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
