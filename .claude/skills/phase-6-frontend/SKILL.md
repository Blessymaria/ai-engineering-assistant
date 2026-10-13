---
name: phase-6-frontend
description: Phase 6 of the AI Engineering Assistant - the single-screen React UI (repository bar, chat with Markdown and Mermaid, live activity panel, history, suggestions) and its API. Use when changing the frontend or the HTTP endpoints it calls (frontend/src, backend/app/api).
---

# Phase 6: the single-screen UI

`CLAUDE.md` and `docs/PLAN.md` are the source of truth.

## Rules

- One screen: repository bar, chat, activity panel. React + TypeScript (Vite), react-markdown, Mermaid. Plain CSS
  with tokens in `index.css`; no UI framework.
- Answers render Markdown; citations `[E3, path:line]` become links that open the full evidence. If a Mermaid diagram
  fails to render, show its source.
- The activity panel shows actions only (tool calls, gaps, created tools, rewrites), never model reasoning. Clicking a
  step opens its full result, or a created tool's code and test run.

## Decisions to keep

- `POST /api/ask` streams Server-Sent Events; the browser parses the stream itself (EventSource is GET-only). Events
  are folded into steps by the pure reducer in `events.ts`, which is also how saved answers replay from History.
- A status label must reflect what actually happened: "locations checked" shows only when the saved answer recorded a
  check result (old answers replayed from History showed it wrongly once).
- Suggested questions and the repository intro come from the backend (graph-derived, model-written intro cached per
  commit); recent repositories and history are stored by the backend, not in the browser.

## Checks

- `npm.cmd run build` and `npm.cmd run lint` clean after every change (lint flags `setState` inside effects; derive
  state instead).
- Look at the result, not only the build: use the `ui-screenshots` skill for a headless-Edge screenshot and say that
  you did. Vite reloads frontend changes itself; backend changes need a restart (`start-app`).
- Keep the UI professional and calm: Blessy asked for a polished look and for removing decorative touches (arrow
  markers, "auto-generated" labels) that read as immature.
