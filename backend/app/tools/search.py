"""search_code: ranked lexical search over graph symbols, routes, docs and source lines."""

import bisect
import re

from app.tools.repo import LoadedRepo, ToolError

MAX_LIMIT = 30
LINES_PER_FILE = 3
SKIP_TEXT = (".lock", "package-lock.json")  # huge and noisy
WORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")  # HTTPException -> HTTP, Exception
ROUTE_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|WEBSOCKET)?\s*(/\S*)$", re.IGNORECASE)


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def tokens(text: str) -> set[str]:
    """Lower-case word stems; splits snake_case, CamelCase and dotted names."""
    return {_stem(w.lower()) for w in WORD_RE.findall(text) if len(w) > 1}


def _route_key(text: str) -> tuple[str, str] | None:
    match = ROUTE_RE.match(text.strip())
    if not match:
        return None
    path = match.group(2).rstrip("/") or "/"
    return (match.group(1) or "").upper(), path.lower()


def _index(repo: LoadedRepo) -> dict:
    """Token sets for nodes and source lines, built once per repository."""
    cached = getattr(repo, "_search_index", None)
    if cached:
        return cached
    nodes = []
    for node_id, d in repo.graph.nodes(data=True):
        if d["kind"] not in ("module", "class", "function", "route", "doc"):
            continue
        nodes.append((node_id, d, tokens(d.get("name", "")), tokens(node_id + " " + d.get("path", "")),
                      tokens(d.get("docstring", ""))))

    # Innermost enclosing symbol for each source line
    spans: dict[str, list[tuple[int, int, str]]] = {}
    for node_id, d in repo.graph.nodes(data=True):
        if d["kind"] in ("class", "function") and "path" in d:
            spans.setdefault(d["path"], []).append((d["start"], d["end"], node_id))
    for spans_in_file in spans.values():
        spans_in_file.sort()

    lines = []
    for path in repo.files:
        if path.endswith(SKIP_TEXT):
            continue
        try:
            text = repo.text(path)
        except ToolError:
            continue
        for n, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                lines.append((path, n, line, tokens(line)))
    repo._search_index = {"nodes": nodes, "lines": lines, "spans": spans}
    return repo._search_index


def _enclosing(spans: list[tuple[int, int, str]], line: int) -> str | None:
    best = None
    for start, end, node_id in spans[: bisect.bisect_right(spans, (line, float("inf"), ""))]:
        if start <= line <= end:
            best = node_id  # later starts are nested deeper
    return best


def search_code(repo: LoadedRepo, query: str, limit: int = 10) -> dict:
    query = query.strip()
    if not query:
        raise ToolError("query is empty")
    limit = max(1, min(limit, MAX_LIMIT))
    index = _index(repo)
    q_lower = query.lower()
    q_tokens = tokens(query)
    q_route = _route_key(query)
    results = []

    for node_id, d, name_t, id_t, doc_t in index["nodes"]:
        score = 0.0
        name = d.get("name", "")
        if name.lower() == q_lower or node_id.lower() == q_lower or node_id.lower().endswith("." + q_lower):
            score = 100
        elif d["kind"] == "route" and q_route:
            method, path = _route_key(name) or ("", "")
            if path == q_route[1] and q_route[0] in ("", method):
                score = 100 if q_route[0] else 90
        if not score and q_tokens:
            in_name = len(q_tokens & name_t) / len(q_tokens)
            score = (30 * in_name + 10 * len(q_tokens & id_t) / len(q_tokens)
                     + 5 * len(q_tokens & doc_t) / len(q_tokens))
            if in_name == 1:
                score += 20
            if d["kind"] == "doc" and score:
                score -= 5  # prefer code over docs for equal matches
        if score > 0:
            item = {**repo.node_info(node_id), "score": round(score, 1)}
            if d.get("docstring"):
                item["doc"] = d["docstring"].splitlines()[0][:120]
            results.append(item)

    symbol_lines = {(r.get("path"), r.get("line")) for r in results}
    per_file: dict[str, int] = {}
    for path, n, line, line_t in index["lines"]:
        if (path, n) in symbol_lines or per_file.get(path, 0) >= LINES_PER_FILE:
            continue
        exact = q_lower in line.lower()
        overlap = len(q_tokens & line_t) / len(q_tokens) if q_tokens else 0
        if not exact and overlap < 1:
            continue
        per_file[path] = per_file.get(path, 0) + 1
        item = {"kind": "line", "path": path, "line": n, "score": round(8 * overlap + (6 if exact else 0), 1),
                "snippet": line.strip()[:160]}
        symbol = _enclosing(index["spans"].get(path, []), n)
        if symbol:
            item["in"] = symbol
        results.append(item)

    results.sort(key=lambda r: (-r["score"], r.get("path", ""), r.get("line") or 0))
    return {"query": query, "total": len(results), "results": results[:limit]}
