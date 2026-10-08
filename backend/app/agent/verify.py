"""Checks an answer against the repository and its own evidence, without another model call.

- Every cited `file:line` must be a real file and line, and must lie inside what the cited evidence showed:
  `[E3, app/x.py:120]` is wrong if E3 read lines 1-46 of app/x.py, or never touched app/x.py.
- Every file or folder path the answer names must exist (the evaluation's answers kept naming an
  `app/db/models/` folder that is not in the repository).

This checks that claims point at evidence that covers them, not that the evidence means what the sentence
says; that would need a second model reading every claim.
"""

import re

from app.agent.evidence import CITATION_GROUP_RE, EVIDENCE_ID_RE, EvidenceStore
from app.tools.repo import LoadedRepo

LOCATION_RE = re.compile(r"([\w./-]+\.\w+):(\d+)(?:\s*-\s*(\d+))?")
# folder or file paths outside citations: a/b, a/b/, a/b.py, b.py (not URLs, not E-ids)
PATH_RE = re.compile(r"(?<![\w/.:-])((?:[\w.-]+/)+[\w.-]*|[\w-]+\.py)(?![\w/])")
SLACK = 2  # lines; models often cite the line above or below a call
MAX_PROBLEMS = 6


def _spans(ev, repo: LoadedRepo) -> list[tuple[str, int, int]]:
    """(path, first, last) line ranges an evidence item showed."""
    spans: list[tuple[str, int, int]] = []
    graph = repo.graph

    def node_span(node_id: str | None) -> tuple[str, int, int] | None:
        d = graph.nodes.get(node_id) if node_id else None
        if d and d.get("path") and d.get("start"):
            return d["path"], d["start"], d.get("end") or d["start"]
        return None

    def walk(value, caller: str | None) -> None:
        if isinstance(value, dict):
            if value.get("path") and isinstance(value.get("start"), int) and isinstance(value.get("end"), int):
                spans.append((value["path"], value["start"], value["end"]))  # read_file
            elif value.get("path") and isinstance(value.get("line"), int):
                span = node_span(value.get("id"))
                spans.append(span or (value["path"], value["line"], value.get("end") or value["line"]))
            if isinstance(value.get("call_line"), int):
                where = node_span(value.get("via") or caller)
                if where:
                    spans.append((where[0], value["call_line"], value["call_line"]))
            for item in value.values():
                walk(item, caller)
        elif isinstance(value, list):
            for item in value:
                walk(item, caller)

    result = ev.result if isinstance(ev.result, dict) else {}
    start_node = result.get("node", {}).get("id") if isinstance(result.get("node"), dict) else None
    walk(result, start_node)
    return spans


def _covered(spans: list[tuple[str, int, int]], path: str, first: int, last: int) -> bool:
    return any(p == path and s - SLACK <= first and last <= e + SLACK for p, s, e in spans)


def _known_folders(repo: LoadedRepo) -> set[str]:
    folders = set()
    for f in repo.files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            folders.add("/".join(parts[:i]))
    return folders


def check_answer(answer: str, store: EvidenceStore, repo: LoadedRepo) -> list[str]:
    """Problems with the answer's locations and paths; empty when everything checks out."""
    problems: list[str] = []
    files = set(repo.files)
    totals: dict[str, int] = {}

    def total_lines(path: str) -> int:
        if path not in totals:
            try:
                totals[path] = len(repo.text(path).splitlines())
            except Exception:
                totals[path] = 0
        return totals[path]

    for group in CITATION_GROUP_RE.findall(answer):
        ids = [i for i in EVIDENCE_ID_RE.findall(group) if i in store.items]
        for path, a, b in LOCATION_RE.findall(group):
            path = path[2:] if path.startswith("./") else path
            first = int(a)
            last = int(b) if b else first
            if path not in files:
                problems.append(f"[{group}] cites {path}, which is not a file in the repository")
            elif first < 1 or last > total_lines(path):
                problems.append(f"[{group}] cites {path}:{a}{'-' + b if b else ''}, but the file has "
                                f"{total_lines(path)} lines")
            elif ids and not any(_covered(_spans(store.items[i], repo), path, first, last) for i in ids):
                problems.append(f"[{group}]: {', '.join(ids)} did not show {path}:{a}{'-' + b if b else ''}; cite "
                                f"the evidence that contains those lines")

    folders = _known_folders(repo)
    outside = CITATION_GROUP_RE.sub(" ", answer)  # paths inside citations were checked above
    outside = re.sub(r"https?://\S+", " ", outside)
    quoted = {q.strip() for q in re.findall(r"`([^`\s]+)`", outside)}
    for raw in dict.fromkeys(PATH_RE.findall(outside)):
        path = raw.strip(".").rstrip("/")
        looks_like_path = raw in quoted or raw.endswith("/") or raw.count("/") >= 2 or re.search(r"\.\w{1,5}$", raw)
        if not path or not looks_like_path:
            continue  # prose such as "request/response"
        # a name relative to a folder mentioned nearby ("contains `routes/`" under `app/api/`) is fine if any
        # file or folder ends with it; a wrong full path ("app/db/models/") still matches nothing
        if path in files or path in folders or any(p.endswith("/" + path) for p in files | folders):
            continue
        problems.append(f"names `{raw}`, which does not exist in the repository")
    return problems[:MAX_PROBLEMS]
