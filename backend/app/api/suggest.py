"""Example questions for whatever repository is loaded, built from its graph (not by the model).

Every name in a suggestion is a real route, function or module of that repository, so the
UI can offer good starting questions for a repository nobody has seen before.
"""

from collections import Counter

import networkx as nx

MAX_SUGGESTIONS = 5
MIN_NAME_LEN = 4


def _is_test(node_id: str, data: dict) -> bool:
    path = data.get("path", "")
    return (path.startswith(("tests/", "test/")) or "/tests/" in path or "/test/" in path
            or data.get("name", "").startswith("test") or ".tests." in node_id or node_id.startswith("tests."))


def _code(graph: nx.MultiDiGraph, kind: str) -> list[tuple[str, dict]]:
    return [(n, d) for n, d in graph.nodes(data=True) if d["kind"] == kind and not _is_test(n, d)]


def _out_calls(graph: nx.MultiDiGraph, node: str) -> int:
    return sum(1 for _, _, d in graph.out_edges(node, data=True) if d["kind"] == "CALLS")


def suggest_questions(graph: nx.MultiDiGraph) -> list[str]:
    suggestions = ["How is this project organised? What are the main packages and what does each do?"]
    functions = {n: d for n, d in _code(graph, "function") if len(d.get("name", "")) >= MIN_NAME_LEN
                 and not d["name"].startswith("_")}

    # A route whose handler does the most work: the richest flow to trace
    routes = []
    for route, data in _code(graph, "route"):
        handlers = [v for _, v, d in graph.out_edges(route, data=True) if d["kind"] == "HANDLES"]
        if handlers:
            routes.append((_out_calls(graph, handlers[0]), data["name"].startswith(("POST", "PUT")), data["name"]))
    if routes:
        methods, _, path = max(routes)[2].partition(" ")
        method = "POST" if "POST" in methods.split("|") else methods.split("|")[0]  # "GET|POST" -> the action
        suggestions.append(f"What happens when {method} {path} is called?")

    # The function the rest of the code relies on most (confirmed calls from non-test code)
    called = Counter(
        v for u, v, d in graph.edges(data=True)
        if d["kind"] == "CALLS" and d.get("status") == "resolved" and v in functions
        and not _is_test(u, graph.nodes[u])
    )
    most_called = called.most_common(1)[0][0] if called else None
    if most_called:
        suggestions.append(f"What does {functions[most_called]['name']} do, and which functions call it?")

    # The module most other modules import
    modules = {n for n, _ in _code(graph, "module")}
    imported = Counter(
        v for u, v, d in graph.edges(data=True)
        if d["kind"] == "IMPORTS" and v in modules and u in modules and u != v and "." in v
    )
    if imported:
        suggestions.append(f"Which modules depend on {imported.most_common(1)[0][0]}?")

    # Git history of a central function: the capability-gap demonstration
    if graph.graph.get("commit"):
        target = most_called or max(functions, key=lambda n: _out_calls(graph, n), default=None)
        if target:
            data = functions[target]
            suggestions.append(f"When was the {data['name']} function in {data['path']} last changed, and by whom?")

    return suggestions[:MAX_SUGGESTIONS]
