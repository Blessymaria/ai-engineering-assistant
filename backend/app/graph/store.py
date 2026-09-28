"""Save and load the code graph as NetworkX node-link JSON."""

import json
from pathlib import Path

import networkx as nx


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(graph, edges="edges")
    path.write_text(json.dumps(data), encoding="utf-8")


def load_graph(path: Path) -> nx.MultiDiGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    return nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")


def graph_path(workspace: Path, root: Path, commit: str | None) -> Path:
    """One graph file per repository and commit."""
    return workspace / "graphs" / f"{root.name}-{(commit or 'local')[:12]}.json"
