"""Build a Mermaid flowchart from the graph relationships the agent actually visited.

Done in code rather than by the model: the small model rarely produced diagrams, and this
guarantees the diagram only contains nodes found in the evidence. Resolved calls are solid
lines; ambiguous and unresolved calls are dashed.
"""

from app.agent.evidence import EvidenceStore

MAX_EDGES = 30
FLOW_RELATIONS = {"callees", "callers", "handlers"}
DEPENDENCY_RELATIONS = {"imports", "imported_by"}


def _label(node_id: str, name: str | None) -> str:
    if node_id.startswith("route:"):
        return name or node_id
    if node_id.startswith("unresolved:"):
        return node_id.split(":", 1)[1] + " ?"
    parts = node_id.split(".")
    # Class.method reads better than a bare method name
    text = ".".join(parts[-2:]) if len(parts) > 2 and parts[-2][:1].isupper() else parts[-1]
    return text.replace('"', "'")


def build_mermaid(store: EvidenceStore) -> str | None:
    """A flowchart from query_graph evidence, or None if there is nothing to draw."""
    edges: list[tuple[str, str, str]] = []  # (from, to, status)
    labels: dict[str, str] = {}
    for ev in store.items.values():
        if ev.tool != "query_graph":
            continue
        result = ev.result
        relation = result["relation"]
        if relation not in FLOW_RELATIONS | DEPENDENCY_RELATIONS:
            continue
        start = result["node"]
        labels.setdefault(start["id"], _label(start["id"], start.get("name")))
        for item in result["results"]:
            if item["id"].startswith("ext:"):
                continue  # library calls add noise without explaining the repository
            labels.setdefault(item["id"], _label(item["id"], item.get("name")))
            parent = item.get("via", start["id"])
            status = item.get("status", "resolved")
            if relation in ("callers", "imported_by") or (relation == "handlers" and item["id"].startswith("route:")):
                edge = (item["id"], parent, status)  # arrows follow the call / import / route -> handler
            else:
                edge = (parent, item["id"], status)
            if edge not in edges:
                edges.append(edge)
    if not edges:
        return None

    ids = {node: f"n{i}" for i, node in enumerate(dict.fromkeys(n for e in edges[:MAX_EDGES] for n in e[:2]))}
    lines = ["flowchart TD"]
    for node, short in ids.items():
        lines.append(f'    {short}["{labels.get(node, node)}"]')
    for src, dst, status in edges[:MAX_EDGES]:
        arrow = "-->" if status == "resolved" else f"-.->|{status}|"
        lines.append(f"    {ids[src]} {arrow} {ids[dst]}")
    if len(edges) > MAX_EDGES:
        lines.append(f'    more["... {len(edges) - MAX_EDGES} more edges"]')
    return "\n".join(lines)
