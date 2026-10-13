---
name: phase-4-agent-loop
description: Phase 4 of the AI Engineering Assistant - the custom agent loop, action parsing, evidence store, citations, answer verification, the Ollama provider and SSE streaming. Use when changing how the agent decides, what the model sees, prompts, citations or answer checks (backend/app/agent, backend/app/llm, POST /api/ask).
---

# Phase 4: the agent loop

`CLAUDE.md` and `docs/PLAN.md` are the source of truth.

## Rules

- **No agent or LLM orchestration frameworks** (LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex agents). The loop
  is plain Python.
- Every model reply becomes exactly one action: `ToolCall`, `CapabilityGap` (reserved `report_capability_gap` schema,
  never executed as a tool), `FinalAnswer`, or `Invalid` (returned to the model with the error).
- Sequential tool calls, at most 12 rounds; at the limit, a forced answer that states what is unresolved.
- Full results stay backend-side as evidence `E1, E2, ...`; the model sees compact versions, and results older than
  the last 3 shrink to a one-line summary.
- Model calls: temperature 0, `think: false`, capped `num_predict`, context 16,384.

## Answer checks (code, not another model)

- An answer with no evidence and no reported gap is sent back once ("look at the code first"); it costs about 10 s
  and is what keeps runtime-state questions from being answered from memory.
- Citations: cited ids must exist; each cited `path:line` must exist and lie inside what its evidence showed; every
  file or folder named must exist (shortened folder names may match by suffix). One rewrite on failure; remaining
  problems are shown with the answer.
- The Mermaid diagram and the "not statically confirmed" list are built from the evidence by code; the small model
  never drew a diagram reliably.

## Lessons

- **Prefer deterministic checks to prompt tuning.** In round 5 a runtime-data rule stopped the git-history gap from
  being reported at all; prompt changes traded one behaviour for another. Tune prompts only to describe tools or
  separate cases clearly, and re-measure.
- Compact graph results must say both "defined at" and "call at" (wrong call-site citations otherwise).
- A small model picks the wrong relation (callers instead of callees) or stops early; that is recorded as a
  limitation, not hidden.

## Done when

`test_agent.py` and `test_verify.py` cover the change with a scripted fake model (exact message assertions where the
prompt matters), a real question on the demo repository is checked by hand against the source, and the measured
effect is in the DEVLOG.
