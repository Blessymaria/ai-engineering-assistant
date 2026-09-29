"""Create, validate, test-run and register a new tool when the agent reports a capability gap.

Flow: ask the LLM for a templated tool (JSON-schema output) -> static check -> validate the
example input -> test run in the container -> check the output is a JSON object -> one retry
with the errors -> register for the session and save code + validation result to disk.
"""

import json
import re
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.agent.actions import GAP_TOOL_NAME, CapabilityGap
from app.llm.base import LLMProvider
from app.runner.context import ToolContext
from app.runner.docker import DockerRunner
from app.toolfactory.static_check import ALLOWED_IMPORTS, static_check
from app.tools.registry import CORE_TOOLS, validate_args
from app.tools.repo import ToolError

MAX_ATTEMPTS = 2  # first try + one retry
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "input_schema": {"type": "object"},
        "example_input": {"type": "object"},
        "code": {"type": "string"},
    },
    "required": ["name", "description", "input_schema", "example_input", "code"],
}

EXAMPLE_BODY = '''counts = {}
for node in ctx.list_nodes("function"):
    counts[node["path"]] = counts.get(node["path"], 0) + 1
top = sorted(counts.items(), key=lambda kv: -kv[1])[:args.get("limit", 5)]
return {"files": len(counts), "top": [{"path": p, "functions": n} for p, n in top]}'''

PROMPT = """Write a new Python tool as the BODY of `def run(args, ctx):`. It must return a dict.

Needed capability: {missing}
Why the existing tools are not enough: {reason}
Example input from the agent: {example}

`ctx` is the only way to reach the repository. Its methods (all return JSON data):
- ctx.search_code(query, limit=10) -> {{"results": [{{"id", "kind", "name", "path", "line"}}, ...]}}
- ctx.query_graph(node, relation, depth=1) -> {{"node": {{...}}, "results": [{{"id", "path", "line", "status"}}, ...]}}
  relations: callers, callees, imports, imported_by, contains, inherits, subclasses, handlers, mentions
- ctx.read_file(path, start=1, end=None) -> {{"content": "  12| code", "total_lines": n}}
- ctx.list_files(path=".", depth=2) -> {{"entries": [{{"path", "type"}}, ...]}}
- ctx.list_nodes(kind) -> [{{"id", "name", "path", "line", "end"}}, ...]   kind: module | class | function | route
- ctx.git_log(path, limit=10) -> [{{"commit", "author", "email", "date", "subject"}}, ...]   newest first
- ctx.git_blame(path, start, end) -> [{{"line", "commit", "author", "date", "summary", "text"}}, ...]
There are no other ctx methods.

Rules: only import {imports} (inside the body). Do not use open, eval, exec, getattr, os, sys, subprocess,
or any name with double underscores. Keep the body under 25 lines. Read inputs from `args`.

Example tool body (counts functions per file, input {{"limit": 5}}):
{example_body}

Reply with JSON: name (snake_case), description (one line), input_schema (JSON schema with "properties"),
example_input (an object that works on THIS repository), code (the body only)."""

RETRY = """That tool did not pass validation:
{errors}
Fix it and reply with the full JSON again (name, description, input_schema, example_input, code)."""


@dataclass
class GeneratedTool:
    name: str
    description: str
    parameters: dict
    source: str
    example_input: dict
    test_output: object
    runner: DockerRunner = field(repr=False)
    ctx: ToolContext = field(repr=False)

    def run(self, args: dict) -> dict:
        args = validate_args(self.parameters, dict(args))
        outcome = self.runner.run(self.source, args, self.ctx.handle)
        if not outcome.ok:
            raise ToolError(f"{self.name} failed: {outcome.error}")
        result = outcome.result
        return result if isinstance(result, dict) else {"result": result}

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass
class CreationResult:
    tool: GeneratedTool | None
    attempts: list[dict]
    audit_dir: Path | None
    seconds: float

    @property
    def errors(self) -> list[str]:
        return self.attempts[-1]["errors"] if self.attempts else ["no attempt made"]


def wrap_body(code: str) -> str:
    """Place the model's body into the fixed template (a full `def run` is accepted too)."""
    code = textwrap.dedent(code.replace("\t", "    ")).strip("\n")
    if re.match(r"^def run\(\s*args\s*,\s*ctx\s*\)", code):
        return code + "\n"
    return "def run(args, ctx):\n" + textwrap.indent(code, "    ") + "\n"


def normalise_schema(schema: dict) -> dict:
    """Accept the shorthand small models often produce, e.g. {"symbol": "string"}."""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}, "required": []}
    props = schema.get("properties")
    if not isinstance(props, dict):
        props = {k: (v if isinstance(v, dict) else {"type": str(v)}) for k, v in schema.items()
                 if k not in ("type", "required")}
    clean = {}
    for key, spec in props.items():
        spec = spec if isinstance(spec, dict) else {"type": str(spec)}
        kind = spec.get("type", "string")
        kind = {"str": "string", "int": "integer", "number": "integer", "bool": "boolean", "list": "array",
                "dict": "object"}.get(kind, kind)
        clean[key] = {"type": kind if kind in ("string", "integer", "boolean", "array", "object") else "string"}
    required = [k for k in schema.get("required", list(clean)) if k in clean] if isinstance(
        schema.get("required", []), list) else list(clean)
    return {"type": "object", "properties": clean, "required": required}


def make_factory(repo, llm: LLMProvider, workspace: Path) -> "ToolFactory | None":
    """A factory using the Docker runner, or None if the runner image is not available."""
    runner = DockerRunner()
    if not runner.available():
        return None
    return ToolFactory(llm, runner, ToolContext(repo), workspace / "tools")


class ToolFactory:
    def __init__(self, llm: LLMProvider, runner: DockerRunner, ctx: ToolContext, audit_root: Path):
        self.llm = llm
        self.runner = runner
        self.ctx = ctx
        self.audit_root = audit_root
        self.created: dict[str, GeneratedTool] = {}

    def _validate(self, spec: dict) -> tuple[GeneratedTool | None, list[str], dict]:
        errors: list[str] = []
        name = str(spec.get("name", "")).strip()
        if not NAME_RE.match(name):
            errors.append(f"name {name!r} must be snake_case, 3-41 characters")
        if name in CORE_TOOLS or name == GAP_TOOL_NAME:
            errors.append(f"name {name!r} is already used by a core tool")
        parameters = normalise_schema(spec.get("input_schema", {}))
        example = spec.get("example_input") if isinstance(spec.get("example_input"), dict) else {}
        try:
            example = validate_args({**parameters, "additionalProperties": False}, dict(example))
        except ToolError as err:
            errors.append(f"example_input does not match input_schema: {err}")
        source = wrap_body(str(spec.get("code", "")))
        errors += static_check(source)
        test = {"input": example}
        if errors:
            return None, errors, test
        outcome = self.runner.run(source, example, self.ctx.handle)
        test.update(ok=outcome.ok, output=outcome.result, error=outcome.error, seconds=outcome.seconds,
                    ctx_calls=outcome.ctx_calls)
        if not outcome.ok:
            return None, [f"test run on example_input failed: {outcome.error}"], test
        if not isinstance(outcome.result, dict) or not outcome.result:
            return None, [f"run() must return a non-empty dict, got {type(outcome.result).__name__}: "
                          f"{json.dumps(outcome.result)[:200]}"], test
        tool = GeneratedTool(name, str(spec.get("description", "")).strip()[:200] or name, parameters, source,
                             example, outcome.result, self.runner, self.ctx)
        return tool, [], test

    def create(self, gap: CapabilityGap) -> CreationResult:
        start = time.perf_counter()
        messages = [{"role": "user", "content": PROMPT.format(
            missing=gap.missing_capability, reason=gap.reason, example=gap.example_input,
            imports=", ".join(sorted(ALLOWED_IMPORTS)), example_body=textwrap.indent(EXAMPLE_BODY, "    "))}]
        attempts: list[dict] = []
        tool = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            reply = self.llm.chat(messages, max_tokens=1500, json_schema=SPEC_SCHEMA)
            try:
                spec = json.loads(reply.content)
                if not isinstance(spec, dict):
                    raise ValueError("reply is not a JSON object")
            except (json.JSONDecodeError, ValueError) as err:
                spec, errors, test = {}, [f"reply is not valid JSON ({err}); was it cut off?"], {}
            else:
                tool, errors, test = self._validate(spec)
            attempts.append({"attempt": attempt, "spec": spec, "raw": reply.content if not spec else None,
                             "errors": errors, "test": test, "llm_seconds": reply.seconds})
            if tool:
                break
            messages += [{"role": "assistant", "content": reply.content},
                         {"role": "user", "content": RETRY.format(errors="\n".join(f"- {e}" for e in errors))}]
        if tool:
            self.created[tool.name] = tool
        audit = self._save_audit(gap, attempts, tool)
        return CreationResult(tool, attempts, audit, round(time.perf_counter() - start, 1))

    def _save_audit(self, gap: CapabilityGap, attempts: list[dict], tool: GeneratedTool | None) -> Path:
        name = tool.name if tool else "failed"
        folder = self.audit_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        if tool:
            (folder / "tool.py").write_text(tool.source, encoding="utf-8")
        record = {"gap": vars(gap), "created": tool is not None, "tool": name if tool else None,
                  "parameters": tool.parameters if tool else None, "attempts": attempts}
        (folder / "validation.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return folder
