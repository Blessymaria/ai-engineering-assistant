---
name: ui-screenshots
description: Take screenshots of the running AI Engineering Assistant UI with headless Edge (no browser tools needed), to check a UI change visually or to see what a page shows. Use after frontend changes, or when a visual check of the app is needed.
---

# UI screenshots with headless Edge

Tests and a clean build do not show what the page looks like; check it visually after UI changes, and say whether
you did. Screenshots for documents are taken by Blessy (see `project-report`); this skill is for your own checks.

## Simple capture

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 --virtual-time-budget=8000 --screenshot="<scratchpad>\page.png" http://localhost:5173/
```

Then read the PNG to look at it.

## Clicking through the UI

`scripts/shot.mjs` drives headless Edge over the DevTools protocol (Node 24 has `fetch` and `WebSocket` built in).
Each argument is a step: a JavaScript expression run in the page, `wait:<ms>`, or `shot:<file.png>`.

```bash
node .claude/skills/ui-screenshots/scripts/shot.mjs \
  "document.querySelectorAll('.repo-card .link-button')[1].click()" "wait:1500" "shot:history.png" \
  "document.querySelector('.history-open').click()" "wait:2500" "shot:answer.png"
```

Useful selectors: `.repo-card .link-button` (0 = Change, 1 = History), `.history-open`, `.example` (suggested
questions), `.ask button` (Suggestions, Ask), `.combo input` (repository input), `.recent-item`, `.step.clickable`.

To type into a React input, set the value through the native setter and dispatch an input event:
`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'text'); el.dispatchEvent(new Event('input',{bubbles:true}))`.

Headless Edge does not fire focus events reliably, so open dropdowns by clicking their trigger. Run the script from
the scratchpad so the PNGs land there, not in the repository.
