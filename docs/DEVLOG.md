# Development log

## 2026-09-28 — Setup: add project brief, technical plan and devlog
- Changes: `CLAUDE.md`, `docs/PLAN.md`, `docs/DEVLOG.md`, `.gitignore`
- Decisions: added a hard rule against Claude/Anthropic attribution (`.claude/settings.local.json` is git-ignored). Plan and devlog live in `docs/` to match the proposed layout; added `node_modules/` and `workspace/` (cloned repositories) to `.gitignore`; `.env` and `.venv` were already ignored by the Python template.
- Verified: `git status` shows only the intended files; no secrets committed.
- Issues / next: start phase 1 (setup) in plan mode.
