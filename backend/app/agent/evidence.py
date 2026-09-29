"""Evidence store: full tool results stay here; the model sees compact text."""

import json
import re
from dataclasses import dataclass

MAX_SEARCH_ITEMS = 8
MAX_GRAPH_ITEMS = 25
MAX_FILE_LINES = 60
MAX_LIST_ENTRIES = 60
MAX_CHARS = 3500
CITATION_GROUP_RE = re.compile(r"\[([^\[\]]*)\]")
EVIDENCE_ID_RE = re.compile(r"\bE\d+\b")


@dataclass
class Evidence:
    id: str
    tool: str
    args: dict
    result: dict
    summary: str  # one line, used once the result is old

    def to_dict(self) -> dict:
        return {"id": self.id, "tool": self.tool, "args": self.args, "summary": self.summary, "result": self.result}


class EvidenceStore:
    def __init__(self) -> None:
        self.items: dict[str, Evidence] = {}

    def add(self, tool: str, args: dict, result: dict) -> Evidence:
        ev_id = f"E{len(self.items) + 1}"
        ev = Evidence(ev_id, tool, args, result, summarise(tool, args, result))
        self.items[ev_id] = ev
        return ev


def _loc(item: dict) -> str:
    return f"{item['path']}:{item['line']}" if item.get("path") else ""


def _args_text(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def summarise(tool: str, args: dict, result: dict) -> str:
    head = f"{tool}({_args_text(args)})"
    if tool == "search_code":
        top = result["results"][0] if result["results"] else None
        best = f"; top: {top.get('id') or _loc(top)}" if top else ""
        return f"{head}: {result['total']} matches{best}"
    if tool == "query_graph":
        return f"{head}: {len(result['results'])} {result['relation']} of {result['node']['id']}"
    if tool == "read_file":
        return f"{head}: lines {result['start']}-{result['end']} of {result['total_lines']}"
    if tool == "list_files":
        return f"{head}: {len(result['entries'])} entries"
    return f"{head}: {len(json.dumps(result))} chars of output"


def compact(tool: str, result: dict) -> str:
    """Short text version of a result for the model's context."""
    lines: list[str] = []
    if tool == "search_code":
        lines.append(f"{result['total']} matches for {result['query']!r}:")
        for r in result["results"][:MAX_SEARCH_ITEMS]:
            if r["kind"] == "line":
                where = f" in {r['in']}" if r.get("in") else ""
                lines.append(f"- line {_loc(r)}{where}: {r['snippet'][:100]}")
            else:
                doc = f" - {r['doc'][:80]}" if r.get("doc") else ""
                lines.append(f"- {r['kind']} {r['id']} ({_loc(r)}){doc}")
    elif tool == "query_graph":
        node = result["node"]
        lines.append(f"{result['relation']} of {node['id']} ({_loc(node)}), depth {result['depth']}:")
        for r in result["results"][:MAX_GRAPH_ITEMS]:
            status = f"[{r['status']}] " if "status" in r else ""
            via = f" via {r['via']}" if r.get("via") else ""
            loc = f" defined at {_loc(r)}" if r.get("path") else ""
            at = ""
            if r.get("call_line"):
                # The call site is in the caller's file: the listed node for callers, the start node for callees.
                caller_path = r.get("path") if result["relation"] == "callers" else (
                    node.get("path") if r["depth"] == 1 else None)
                at = f"; call at {caller_path}:{r['call_line']}" if caller_path else f"; call at line {r['call_line']}"
            lines.append(f"- {status}{r['id']}{loc}{at}{via}")
        if not result["results"]:
            lines.append("- (none)")
        if len(result["results"]) > MAX_GRAPH_ITEMS:
            lines.append(f"... {len(result['results']) - MAX_GRAPH_ITEMS} more not shown")
        for key in ("note_calls", "note"):
            if key in result:
                lines.append(f"Note: {result[key]}")
    elif tool == "read_file":
        content = result["content"].splitlines()
        lines.append(f"{result['path']} lines {result['start']}-{result['end']} of {result['total_lines']}:")
        lines.extend(content[:MAX_FILE_LINES])
        if len(content) > MAX_FILE_LINES:
            lines.append(f"... cut at {MAX_FILE_LINES} lines; read a narrower range to see more")
    elif tool == "list_files":
        lines.append(f"files under {result['path']}:")
        for e in result["entries"][:MAX_LIST_ENTRIES]:
            lines.append(f"- {e['path']}" + (f" ({e['files']} files)" if e["type"] == "dir" else ""))
        if len(result["entries"]) > MAX_LIST_ENTRIES:
            lines.append("... more not shown; list a subfolder")
    else:
        lines.append(json.dumps(result)[:MAX_CHARS])
    text = "\n".join(lines)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n... cut"


def check_citations(answer: str, store: EvidenceStore) -> dict:
    """Which evidence ids the answer cites, and which of those do not exist.

    This proves references are real, not that the evidence supports each claim.
    """
    cited: list[str] = []
    for group in CITATION_GROUP_RE.findall(answer):
        for ev_id in EVIDENCE_ID_RE.findall(group):
            if ev_id not in cited:
                cited.append(ev_id)
    missing = [e for e in cited if e not in store.items]
    return {"cited": cited, "missing": missing, "valid": len(cited) - len(missing), "total": len(cited)}
