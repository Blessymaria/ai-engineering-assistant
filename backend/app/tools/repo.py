"""A loaded repository: its root folder, code graph and cached file text."""

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from app.graph.build import build_graph
from app.graph.store import load_graph
from app.ingest.loader import load_repo
from app.ingest.paths import PathError, check_readable, iter_files

CODE_KINDS = ("module", "class", "function", "route")
MAX_CANDIDATES = 10


class ToolError(ValueError):
    """Bad tool input; the message is shown to the agent so it can recover."""


@dataclass
class LoadedRepo:
    root: Path
    graph: nx.MultiDiGraph
    files: list[str]
    _text: dict[str, str] = field(default_factory=dict, repr=False)
    _search_index: dict | None = field(default=None, repr=False)  # built by search_code

    @classmethod
    def build(cls, source: str, workspace: Path) -> "LoadedRepo":
        repo = load_repo(source, workspace)
        return cls(repo.root, build_graph(repo), repo.files)

    @classmethod
    def from_graph_file(cls, path: Path) -> "LoadedRepo":
        graph = load_graph(path)
        root = Path(graph.graph["root"])
        return cls(root, graph, iter_files(root))

    def text(self, rel_path: str) -> str:
        """File text via the path-safety rules; raises ToolError if not allowed."""
        rel_path = normalise_path(rel_path)
        if rel_path not in self._text:
            try:
                path = check_readable(self.root, rel_path)
            except PathError as err:
                raise ToolError(str(err)) from err
            self._text[rel_path] = path.read_text(encoding="utf-8", errors="replace")
        return self._text[rel_path]

    def node_info(self, node_id: str) -> dict:
        d = self.graph.nodes[node_id]
        info = {"id": node_id, "kind": d["kind"], "name": d.get("name", node_id)}
        if "path" in d:
            info["path"] = d["path"]
            info["line"] = d.get("start")
        return info

    def find_node(self, ref: str) -> str:
        """Resolve a node id, a unique dotted suffix, a unique name or a route like 'POST /articles'."""
        ref = ref.strip()
        if ref in self.graph:
            return ref
        candidates = [
            n for n, d in self.graph.nodes(data=True)
            if d["kind"] in CODE_KINDS + ("doc",)
            # route ids end with their handler id, so routes match by name ("POST /x") only
            and ((d["kind"] != "route" and n.endswith("." + ref)) or d.get("name", "").lower() == ref.lower())
        ]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ToolError(f"no node named {ref!r}; use search_code to find the right id")
        shown = sorted(candidates)[:MAX_CANDIDATES]
        raise ToolError(f"{ref!r} matches {len(candidates)} nodes, use one of these ids: {shown}")


def normalise_path(path: str) -> str:
    path = path.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/") or "."
