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
