---
name: phase-1-setup
description: Phase 1 of the AI Engineering Assistant - repository skeleton, backend and frontend apps, local model selection, Ollama, WSL and Docker without admin rights, and Breeze indexing for development. Use when setting up the project or its environment from scratch, choosing or changing the local model, or fixing environment problems.
---

# Phase 1: setup and model selection

`CLAUDE.md` and `docs/PLAN.md` are the source of truth; if this skill and they disagree, they win.

## Rules for this phase

- Start in plan mode: summarise what will be built and which files change, and wait for approval.
- Plan, brief and devlog first (`docs/PLAN.md`, `docs/DEVLOG.md`, `CLAUDE.md`); `.gitignore` covers `.env`,
  `node_modules/`, `.venv/`, `workspace/` and `.claude/settings.local.json`. No Claude or Anthropic attribution
  anywhere (commits, PRs, code, docs).
- No infrastructure outside the plan (no graph or vector databases, no Redis, no microservices). Ask first.
- Breeze is for understanding this codebase during development only; the application never calls Breeze or MCP.

## Environment (Windows 11, no local admin rights, corporate network)

- Python 3.13 (`py -3.13`), Node.js 24 LTS (installed by IT), Git, Ollama.
- Use `npm.cmd`, not `npm`: PowerShell's execution policy blocks `npm.ps1`.
- Containers: Docker Desktop needs admin, so install Docker Engine with apt inside the WSL `Ubuntu` distro and call it
  as `wsl -d Ubuntu -u root -- docker`. Docker Hub is blocked: build the runner image locally
  (`runner-image/build-local.sh`, debootstrap from the Ubuntu mirror).
- `wsl --install` can fail on certificate checks; import Ubuntu 24.04 from cloud-images.ubuntu.com instead.
- Breeze indexing runs inside WSL (`breezeai-cog` cannot build on Windows without MSVC); the API key lives in
  `.breeze.json` outside the repository and is never printed or committed; re-uploads need the old repository deleted
  in the Breeze UI first (HTTP 409 otherwise).

## Model selection

- A one-hour test, recorded in `eval/model_test.py` and `eval/results/model_test.json`: single tool-call choices,
  capability-gap cases and tool-spec generation, at temperature 0 with capped replies.
- Result: `gemma4:e4b` (6/8 correct tool calls, short replies) over `qwen3:4b` (inconsistent; ignored `think: false`).
- Always cap reply length (`num_predict`) and set the context explicitly: Ollama's default 4,096 tokens silently cuts
  the start of long prompts. The project uses 16,384 (`OLLAMA_NUM_CTX`).

## Done when

`pytest` passes, `GET /api/health` returns ok through the Vite proxy, `npm.cmd run build` and `npm.cmd run lint` are
clean, the model choice is recorded with its numbers, and the DEVLOG has an entry for every step.
