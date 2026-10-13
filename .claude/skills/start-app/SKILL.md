---
name: start-app
description: Start, restart or check the AI Engineering Assistant locally on Windows (Ollama, FastAPI backend on port 8000, Vite frontend on port 5173). Use when asked to run, start, restart or check the app, or after backend code changes that the running server must pick up.
---

# Start the app

Blessy sometimes starts the servers by hand (for demos). Before starting or stopping anything, check what is already
running, and if Blessy says "stop, I will start it myself", stop only what was started in this session and give
the exact commands instead.

## Check what is running

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn*' } | Select ProcessId, CommandLine
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
(Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/version).Content   # Ollama
(Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/ps).Content        # loaded model
```

## Start or restart

- **Backend** (no `--reload`, so restart it after backend changes; `Start-Process` keeps it alive after the
  session's command finishes):
  ```powershell
  $b="<repo>\backend"
  Start-Process -FilePath "$b\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--port","8000" -WorkingDirectory $b -WindowStyle Minimized
  ```
  Stop only uvicorn processes (filter on the command line); never kill every `python.exe`.
- **Frontend**: `cd frontend; npm.cmd run dev` (`npm` fails on this machine: PowerShell blocks `npm.ps1`). Vite reloads
  frontend changes itself. If it opens on 5174, something already holds 5173.
- **Restarting the backend also clears validated generated tools** (they are kept in memory per repository and commit).
  Restart deliberately when tool creation must be shown again.

## Verify

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health).Content   # {"status":"ok"}
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/repo).Content     # loaded repository
```

Report: backend OK, frontend URL, Ollama version, which repository is loaded, and anything the user must do next.
