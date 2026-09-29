"""query_graph: follow relationships from one node up to a chosen depth."""

from app.tools.repo import LoadedRepo, ToolError

MAX_DEPTH = 3
MAX_RESULTS = 60

# relation -> (edge kind, direction); "auto" means out from docs/routes, in otherwise
RELATIONS = {
    "callers": ("CALLS", "in"),
    "callees": ("CALLS", "out"),
    "imports": ("IMPORTS", "out"),
    "imported_by": ("IMPORTS", "in"),
    "contains": ("CONTAINS", "out"),
    "inherits": ("INHERITS", "out"),
    "subclasses": ("INHERITS", "in"),
    "handlers": ("HANDLES", "auto"),
    "mentions": ("MENTIONS", "auto"),
}
LEAF_KINDS = ("external", "unresolved")


def query_graph(repo: LoadedRepo, node: str, relation: str, depth: int = 1) -> dict:
    """Breadth-first walk. CALLS edges are only followed further when resolved;
    ambiguous and unresolved calls are listed but not expanded."""
    if relation not in RELATIONS:
        raise ToolError(f"unknown relation {relation!r}; use one of {sorted(RELATIONS)}")
    start = repo.find_node(node)
    depth = max(1, min(depth, MAX_DEPTH))
    kind, direction = RELATIONS[relation]
    if direction == "auto":
        direction = "out" if repo.graph.nodes[start]["kind"] in ("route", "doc") else "in"
    g = repo.graph

    results, seen, frontier, truncated = [], {start}, [start], False
    for level in range(1, depth + 1):
        next_frontier = []
        for current in frontier:
            edges = g.out_edges(current, data=True) if direction == "out" else g.in_edges(current, data=True)
            for u, v, d in sorted(edges, key=lambda e: (e[2].get("line") or 0, e[0], e[1])):
                if d["kind"] != kind:
                    continue
                other = v if direction == "out" else u
                if other in seen:
                    continue
                if len(results) >= MAX_RESULTS:
                    truncated = True
                    break
                seen.add(other)
                item = {**repo.node_info(other), "depth": level}
                if level > 1:
                    item["via"] = current
                if kind == "CALLS":
                    item["status"] = d["status"]
                    item["call_line"] = d["line"]
                    if d["status"] == "ambiguous":
                        item["candidates"] = d.get("candidates", 1)
                results.append(item)
                follow = kind != "CALLS" or d["status"] == "resolved"
                if follow and g.nodes[other]["kind"] not in LEAF_KINDS:
                    next_frontier.append(other)
        frontier = next_frontier

    result = {"node": repo.node_info(start), "relation": relation, "depth": depth, "results": results}
    if truncated:
        result["note"] = f"stopped at {MAX_RESULTS} results; use a lower depth or a more specific node"
    if kind == "CALLS" and any(r["status"] != "resolved" for r in results):
        result["note_calls"] = ("ambiguous/unresolved calls are not confirmed and were not followed; "
                                "read the source to check them")
    return result
