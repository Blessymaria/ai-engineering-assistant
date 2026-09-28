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
