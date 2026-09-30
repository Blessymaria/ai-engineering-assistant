"""The four core tools: names, short descriptions, JSON schemas and dispatch.

Shared by the agent (phase 4) and the generated-tool ToolContext (phase 5).
"""

from dataclasses import dataclass
from typing import Callable

from app.tools.files import list_files, read_file
from app.tools.graph_query import RELATIONS, query_graph
from app.tools.repo import LoadedRepo, ToolError
from app.tools.search import search_code


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., dict]


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


CORE_TOOLS = {
    t.name: t for t in [
        ToolSpec(
            "search_code",
            "Find code by text: symbol names, routes like 'POST /articles', paths, docstrings, docs and source "
            "lines. Returns node ids and file:line matches, best first.",
            _schema({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
            search_code,
        ),
        ToolSpec(
            "query_graph",
            "Follow code relationships from a node id (or unique name): callers, callees, imports, imported_by, "
            "contains, inherits, subclasses, handlers (route <-> handler), mentions (docs <-> code). "
            "Calls have status resolved, ambiguous or unresolved.",
            _schema({
                "node": {"type": "string"},
                "relation": {"type": "string", "enum": sorted(RELATIONS)},
                "depth": {"type": "integer"},
            }, ["node", "relation"]),
            query_graph,
        ),
        ToolSpec(
            "read_file",
            "Read numbered source lines of a repository file (max 120 lines per call; pass start to read further).",
            _schema({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"]),
            read_file,
        ),
        ToolSpec(
            "list_files",
            "List the folder tree under a path (default: repository root).",
            _schema({"path": {"type": "string"}, "depth": {"type": "integer"}}, []),
            list_files,
        ),
    ]
}

JSON_TYPES = {"string": str, "integer": int, "object": dict, "array": list, "boolean": bool}


def validate_args(schema: dict, args: object) -> dict:
    """Check args against a flat object schema; raises ToolError with a readable message."""
    if not isinstance(args, dict):
        raise ToolError("arguments must be a JSON object")
    props = schema.get("properties", {})
    missing = [k for k in schema.get("required", []) if k not in args]
    if missing:
        raise ToolError(f"missing required argument(s): {', '.join(missing)}")
    for key, value in args.items():
        if key not in props:
            raise ToolError(f"unknown argument {key!r}; expected {sorted(props)}")
        expected = props[key].get("type")
        py_type = JSON_TYPES.get(expected)
        # Small models often send numbers as strings, e.g. "10"
        if expected == "integer" and isinstance(value, str) and value.strip().lstrip("-").isdigit():
            args[key] = value = int(value)
        if py_type and (not isinstance(value, py_type) or (py_type is int and isinstance(value, bool))):
            raise ToolError(f"argument {key!r} must be a {expected}")
        if "enum" in props[key] and value not in props[key]["enum"]:
            raise ToolError(f"argument {key!r} must be one of {props[key]['enum']}")
    return args


def run_tool(repo: LoadedRepo, name: str, args: object) -> dict:
    """Validate and run a core tool. Raises ToolError for bad names or arguments."""
    spec = CORE_TOOLS.get(name)
    if spec is None:
        raise ToolError(f"unknown tool {name!r}; available: {sorted(CORE_TOOLS)}")
    args = validate_args(spec.parameters, dict(args) if isinstance(args, dict) else args)
    return spec.fn(repo, **args)
