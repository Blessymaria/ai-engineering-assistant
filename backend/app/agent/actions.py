"""Turn each model reply into exactly one structured action."""

import json
import re
from dataclasses import dataclass

from app.llm.base import LLMReply

GAP_TOOL_NAME = "report_capability_gap"
GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "missing_capability": {"type": "string"},
        "reason": {"type": "string"},
        "example_input": {"type": "string"},
    },
    "required": ["missing_capability", "reason", "example_input"],
}
GAP_TOOL = {
    "type": "function",
    "function": {
        "name": GAP_TOOL_NAME,
        "description": "Use when no available tool can get information you need (e.g. git history, "
                       "checking all functions at once). Say what is missing and why. Never guess instead.",
        "parameters": GAP_SCHEMA,
    },
}


@dataclass
class ToolCall:
    name: str
    args: dict
    note: str = ""  # e.g. "only the first of 2 tool calls was run"


@dataclass
class CapabilityGap:
    missing_capability: str
    reason: str
    example_input: str


@dataclass
class FinalAnswer:
    text: str


@dataclass
class Invalid:
    error: str


Action = ToolCall | CapabilityGap | FinalAnswer | Invalid

JSON_BLOCK_RE = re.compile(r"^```(?:json|tool_code)?\s*(\{.*\})\s*```$", re.DOTALL)


def _tool_call_in_text(content: str) -> tuple[str, dict] | None:
    """Small models sometimes write the call as JSON text instead of a real tool call."""
    text = content.strip()
    match = JSON_BLOCK_RE.match(text)
    if match:
        text = match.group(1)
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    name = data.get("name") or data.get("tool")
    args = data.get("arguments", data.get("parameters", data.get("args")))
    if isinstance(name, str) and isinstance(args, dict):
        return name, args
    return None


def parse_reply(reply: LLMReply, tool_names: set[str]) -> Action:
    calls = [(c.name, c.arguments) for c in reply.tool_calls]
    if not calls:
        in_text = _tool_call_in_text(reply.content)
        if in_text:
            calls = [in_text]
    if not calls:
        if not reply.content.strip():
            return Invalid("empty reply; call a tool or give your answer")
        return FinalAnswer(reply.content.strip())

    name, args = calls[0]
    note = f"only the first of {len(calls)} tool calls was run; call one tool at a time" if len(calls) > 1 else ""
    if name == GAP_TOOL_NAME:
        missing = [k for k in GAP_SCHEMA["required"] if not str(args.get(k, "")).strip()]
        if missing:
            return Invalid(f"{GAP_TOOL_NAME} needs: {', '.join(missing)}")
        return CapabilityGap(str(args["missing_capability"]), str(args["reason"]), str(args["example_input"]))
    if name not in tool_names:
        return Invalid(f"unknown tool {name!r}; available: {sorted(tool_names | {GAP_TOOL_NAME})}")
    return ToolCall(name, args, note)
