# AI Engineering Assistant

Answers questions about unfamiliar Python repositories using a code graph (GraphRAG), a custom agent loop and runtime tool generation. Runs locally with a small model via Ollama.

> Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design and [docs/DEVLOG.md](docs/DEVLOG.md) for progress.

## Prerequisites

- Python 3.13
- Node.js LTS (frontend)
- Docker Desktop (runs generated tools)
- Ollama (local LLM)

## Run

Backend (PowerShell or Git Bash):

```
cd backend
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Check it at http://localhost:8000/api/health. Run tests with `.venv/Scripts/python -m pytest`.

Frontend (in a second terminal, with the backend running):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend on port 8000.

## Assumptions and limitations

TODO (filled in during phase 7).
