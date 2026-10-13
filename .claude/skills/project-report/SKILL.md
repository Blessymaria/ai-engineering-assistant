---
name: project-report
description: Write or revise a project document about the AI Engineering Assistant (technical report, overview, review documentation) and place screenshots in it. Use when Blessy asks for a document, report or write-up, or sends screenshots to add to one.
---

# Project report

## When

Only when asked. After code changes, update repository files (README, DEVLOG, RESULTS) but not the shared documents
unless Blessy asks.

## Audience and voice

- Readers are senior engineers and technical mentors; Blessy is an AI engineer. Use technical terms without
  explaining basics (GraphRAG, SSE, tool calling, sandboxing, deterministic checks), but keep each section readable in
  one pass: short paragraphs, tables and numbered lists over long prose.
- Formal, measured register in the style of a technical project report. State verified facts directly; do not hedge
  with "the source describes" for things that can be checked in the repository.
- Distinguish requirements met (verified in code and tests) from measured answer accuracy (small-sample evaluation).
- Never overstate: "local inference" (repository content never leaves the machine; cloning needs network), "structural
  verification" (not semantic proof), "MVP" (not production-grade).

## Structure

Title block with the repository link, executive summary with a key-measures table, then numbered sections: problem and
requirements; architecture and request lifecycle; technology choices with setup; runtime tool synthesis and
safeguards; UI and demonstrated workflows; evaluation and measured outcomes with performance; engineering process and
constraints (phases, dates, environment limits); limitations and future work (production kept short, outside the
brief); conclusion; appendix with verification notes (final commit, test count, model and versions, dates, when each
figure was captured).

## Numbers

Re-check every number against the source before writing it: test count from a fresh `pytest` run, results from
`eval/RESULTS.md`, timings from the transcripts, dates from git. Keep the same number consistent everywhere (a
latency stated in the summary must match the measured range later).

## Screenshots

- Blessy takes the screenshots; place each next to the claim it supports, with a context sentence before it and an
  italic numbered caption after it ("*Figure N. ...*").
- Verify what a screenshot shows before using it. If the answer in it is wrong, say so and leave it out (or use it as
  a labelled limitation); never caption a wrong result as correct. A wrong `get_user_by_username` answer found this way
  led to a real fix.
- Drop duplicates and superseded images; say which ones and why.
- When a claim has no screenshot behind it, list the missing ones with the exact question to ask and the expected
  answer, in priority order.
- Respect Blessy's own edits in the document: re-read the changes since your last revision and do not overwrite them.
