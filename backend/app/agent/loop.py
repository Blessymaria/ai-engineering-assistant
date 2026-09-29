"""The custom agent loop: plain Python, one tool call per round, at most MAX_ROUNDS rounds."""

import time
from dataclasses import dataclass, field
from typing import Callable

from app.agent.actions import GAP_TOOL, GAP_TOOL_NAME, CapabilityGap, FinalAnswer, Invalid, ToolCall, parse_reply
from app.agent.evidence import EvidenceStore, check_citations, compact
from app.agent.prompts import GAP_UNAVAILABLE, LIMIT_REACHED, NO_TOOL_YET, SYSTEM_PROMPT
from app.llm.base import LLMProvider
from app.tools.registry import CORE_TOOLS, run_tool
from app.tools.repo import LoadedRepo, ToolError

MAX_ROUNDS = 12
RECENT_RESULTS = 3  # tool results older than this shrink to a one-line summary
MAX_TOKENS = 1024


@dataclass
class Event:
    type: str  # started | llm_reply | tool_called | tool_result | tool_error | gap_detected | invalid_action | limit_reached | answer
    data: dict
    t: float = field(default_factory=time.time)


@dataclass
class AgentResult:
    answer: str
    citations: dict
    evidence: EvidenceStore
    rounds: int
    stopped: str  # "answer" | "limit"
    gaps: list[CapabilityGap]
    events: list[Event]
    seconds: float


@dataclass
class _Step:
    assistant: dict
    reply_full: dict
    reply_short: dict | None = None  # used once the step is old


def tool_schemas() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in CORE_TOOLS.values()
    ] + [GAP_TOOL]


def _tool_message(name: str, content: str) -> dict:
    return {"role": "tool", "tool_name": name, "content": content}


def _call_message(name: str, args: dict) -> dict:
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


class Agent:
    def __init__(self, repo: LoadedRepo, llm: LLMProvider, max_rounds: int = MAX_ROUNDS,
                 on_event: Callable[[Event], None] | None = None):
        self.repo = repo
        self.llm = llm
        self.max_rounds = max_rounds
        self.on_event = on_event
        self.events: list[Event] = []

    def _emit(self, type_: str, **data) -> None:
        event = Event(type_, data)
        self.events.append(event)
        if self.on_event:
            self.on_event(event)

    def _messages(self, question: str, steps: list[_Step]) -> list[dict]:
        repo_name = self.repo.root.name
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(repo=repo_name)},
            {"role": "user", "content": question},
        ]
        tool_steps = [i for i, s in enumerate(steps) if s.reply_short is not None]
        old = set(tool_steps[:-RECENT_RESULTS]) if len(tool_steps) > RECENT_RESULTS else set()
        for i, step in enumerate(steps):
            messages.append(step.assistant)
            messages.append(step.reply_short if i in old else step.reply_full)
        return messages

    def run(self, question: str) -> AgentResult:
        start = time.perf_counter()
        store = EvidenceStore()
        steps: list[_Step] = []
        gaps: list[CapabilityGap] = []
        rounds = 0
        nudged = False
        tools = tool_schemas()
        tool_names = set(CORE_TOOLS)
        self._emit("started", question=question, model=self.llm.name, max_rounds=self.max_rounds)

        while True:
            forced = rounds >= self.max_rounds
            messages = self._messages(question, steps)
            if forced:
                self._emit("limit_reached", rounds=rounds)
                messages.append({"role": "user", "content": LIMIT_REACHED})
            reply = self.llm.chat(messages, tools=None if forced else tools, max_tokens=MAX_TOKENS)
            self._emit("llm_reply", seconds=reply.seconds, tokens=reply.tokens, done_reason=reply.done_reason)

            action = FinalAnswer(reply.content.strip()) if forced else parse_reply(reply, tool_names)
            if isinstance(action, FinalAnswer) and not forced and not store.items and not gaps and not nudged:
                # Small models sometimes answer from memory; ask once for evidence first
                # (not after a reported gap: then "unresolved" is the honest answer).
                nudged = True
                action = Invalid(NO_TOOL_YET)

            if isinstance(action, FinalAnswer):
                answer = action.text or "(the model returned an empty answer)"
                citations = check_citations(answer, store)
                self._emit("answer", text=answer, citations=citations, rounds=rounds)
                return AgentResult(answer, citations, store, rounds, "limit" if forced else "answer", gaps,
                                   self.events, round(time.perf_counter() - start, 1))

            rounds += 1
            if isinstance(action, ToolCall):
                self._emit("tool_called", round=rounds, tool=action.name, args=action.args)
                assistant = _call_message(action.name, action.args)
                t0 = time.perf_counter()
                try:
                    result = run_tool(self.repo, action.name, action.args)
                except ToolError as err:
                    self._emit("tool_error", round=rounds, tool=action.name, error=str(err))
                    content = f"Error: {err}"
                    steps.append(_Step(assistant, _tool_message(action.name, content)))
                    continue
                ev = store.add(action.name, action.args, result)
                ms = round((time.perf_counter() - t0) * 1000)
                self._emit("tool_result", round=rounds, tool=action.name, evidence_id=ev.id, summary=ev.summary, ms=ms)
                content = f"[{ev.id}] {compact(action.name, result)}"
                if action.note:
                    content += f"\nNote: {action.note}"
                steps.append(_Step(assistant, _tool_message(action.name, content),
                                   _tool_message(action.name, f"[{ev.id}] (older result) {ev.summary}")))
            elif isinstance(action, CapabilityGap):
                gaps.append(action)
                self._emit("gap_detected", round=rounds, missing_capability=action.missing_capability,
                           reason=action.reason, example_input=action.example_input)
                assistant = _call_message(GAP_TOOL_NAME, {
                    "missing_capability": action.missing_capability, "reason": action.reason,
                    "example_input": action.example_input,
                })
                steps.append(_Step(assistant, _tool_message(GAP_TOOL_NAME, GAP_UNAVAILABLE)))
            else:  # Invalid
                self._emit("invalid_action", round=rounds, error=action.error)
                assistant = {"role": "assistant", "content": reply.content[:500]}
                steps.append(_Step(assistant, {"role": "user", "content": f"Error: {action.error}"}))
