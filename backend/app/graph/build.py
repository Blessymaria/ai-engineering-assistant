"""Build the code graph for a repository.

Usage: python -m app.graph.build <git-url-or-path> [--workspace DIR]
"""

import argparse
from collections import Counter
from pathlib import Path

import networkx as nx

from app.graph.store import graph_path, save_graph
from app.ingest.calls import Resolver, resolve_calls
from app.ingest.docs import SymbolMatcher, mentioned_names, split_sections
from app.ingest.loader import Repo, load_repo
from app.ingest.paths import check_readable
from app.ingest.parser import Module, Route, Symbol, parse_module

DEFAULT_WORKSPACE = Path(__file__).resolve().parents[3] / "workspace"
DOC_SUFFIXES = (".md", ".markdown", ".rst")


def _read(repo: Repo, path: str) -> str:
    return check_readable(repo.root, path).read_text(encoding="utf-8", errors="replace")


def _add_placeholder(graph: nx.MultiDiGraph, node_id: str) -> None:
    if node_id not in graph:
        kind, _, name = node_id.partition(":")
        kind = "external" if kind == "ext" else kind
        graph.add_node(node_id, kind=kind, name=name)


def build_graph(repo: Repo) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(root=str(repo.root), commit=repo.commit)
    modules: dict[str, Module] = {}
    symbols: dict[str, Symbol] = {}
    routes: list[Route] = []

    for path in repo.files:
        if path.endswith(".py"):
            module, syms, rts = parse_module(path, _read(repo, path))
            modules[module.name] = module
            symbols.update((s.id, s) for s in syms)
            routes.extend(rts)

    # Nodes and CONTAINS edges
    for s in symbols.values():
        graph.add_node(s.id, kind=s.kind, name=s.name, path=s.path, start=s.start, end=s.end, docstring=s.docstring)
        if s.parent:
            graph.add_edge(s.parent, s.id, kind="CONTAINS")
    for module in modules.values():
        if module.error:
            graph.nodes[module.name]["error"] = module.error

    resolver = Resolver(modules, symbols)

    # IMPORTS: module -> module (repo) or external package
    for module in modules.values():
        for target, line in module.imported:
            status, node_id = resolver.resolve_dotted(target)
            if status == "unresolved":
                continue
            _add_placeholder(graph, node_id)
            graph.add_edge(module.name, node_id, kind="IMPORTS", line=line)

    # INHERITS: class -> base class
    for s in symbols.values():
        if s.kind == "class" and s.node is not None:
            module = modules[_module_of(s, symbols)]
            resolver.resolve_bases(s, module)
            for base in resolver.bases[s.id]:
                _add_placeholder(graph, base)
                graph.add_edge(s.id, base, kind="INHERITS")

    # HANDLES: route -> handler
    prefixes = _router_prefixes(modules)
    for r in routes:
        module = modules[_module_of(symbols[r.handler], symbols)]
        router = _router_id(r.router, module, modules, prefixes) if r.router else None
        full_path = (prefixes.get(router, "") + r.path) or "/"
        route_id = f"route:{r.method} {full_path} -> {r.handler}"
        graph.add_node(route_id, kind="route", name=f"{r.method} {full_path}", method=r.method,
                       route=full_path, path=r.file, start=r.line, end=r.line)
        graph.add_edge(route_id, r.handler, kind="HANDLES")

    # CALLS with resolution status
    by_module: dict[str, list[Symbol]] = {}
    for s in symbols.values():
        by_module.setdefault(_module_of(s, symbols), []).append(s)
    for name, module in modules.items():
        for call in resolve_calls(resolver, by_module.get(name, []), module):
            for target in call.targets:
                _add_placeholder(graph, target)
                graph.add_edge(call.caller, target, kind="CALLS", status=call.status, line=call.line,
                               candidates=len(call.targets))

    # Documentation sections and MENTIONS
    matcher = SymbolMatcher(list(symbols))
    for path in repo.files:
        if not path.lower().endswith(DOC_SUFFIXES):
            continue
        for sec in split_sections(path, _read(repo, path)):
            graph.add_node(sec.id, kind="doc", name=sec.title, path=sec.path, start=sec.start, end=sec.end)
            for mention in sorted(mentioned_names(sec.text)):
                target = matcher.match(mention)
                if target:
                    graph.add_edge(sec.id, target, kind="MENTIONS")
    return graph


def _router_id(dotted: str, module: Module, modules: dict[str, Module], routers: dict) -> str | None:
    """Map a router expression in `module` (e.g. `articles.router`) to "<module>.<name>"."""
    head, _, rest = dotted.partition(".")
    if head in module.routers and not rest:
        return f"{module.name}.{head}"
    if head not in module.imports:
        return None
    full = f"{module.imports[head]}.{rest}" if rest else module.imports[head]
    for _ in range(5):  # follow re-exports
        if full in routers:
            return full
        mod, _, name = full.rpartition(".")
        full = modules[mod].imports.get(name) if mod in modules else None
        if not full:
            return None
    return None


def _router_prefixes(modules: dict[str, Module]) -> dict[str, str]:
    """Full path prefix of each module-level APIRouter, following include_router() chains.

    Prefixes that are not string constants (e.g. `settings.api_prefix`) are unknown and left out.
    """
    own = {f"{m.name}.{name}": prefix for m in modules.values() for name, prefix in m.routers.items()}
    parent: dict[str, tuple[str, str]] = {}
    for m in modules.values():
        for inc in m.includes:
            p, c = _router_id(inc.parent, m, modules, own), _router_id(inc.child, m, modules, own)
            if p and c and c not in parent:
                parent[c] = (p, inc.prefix)

    def full(router: str, depth: int = 0) -> str:
        up = parent.get(router)
        base = full(up[0], depth + 1) + up[1] if up and depth < 10 else ""
        return base + own.get(router, "")

    return {router: full(router) for router in own}


def _module_of(symbol: Symbol, symbols: dict[str, Symbol]) -> str:
    while symbol.parent:
        symbol = symbols[symbol.parent]
    return symbol.id


def summary(graph: nx.MultiDiGraph) -> str:
    nodes = Counter(kind for _, kind in graph.nodes(data="kind"))
    edges = Counter(kind for *_, kind in graph.edges(data="kind"))
    calls = Counter(d["status"] for *_, d in graph.edges(data=True) if d["kind"] == "CALLS")
    internal = Counter(
        d["status"] for _, v, d in graph.edges(data=True)
        if d["kind"] == "CALLS" and graph.nodes[v]["kind"] not in ("external",)
    )
    errors = [n for n, e in graph.nodes(data="error") if e]
    routes = sorted(d["name"] for _, d in graph.nodes(data=True) if d["kind"] == "route")
    total = sum(calls.values()) or 1
    lines = [
        f"root:   {graph.graph['root']}",
        f"commit: {graph.graph['commit']}",
        "nodes:  " + ", ".join(f"{k}={v}" for k, v in sorted(nodes.items())),
        "edges:  " + ", ".join(f"{k}={v}" for k, v in sorted(edges.items())),
        "calls:  " + ", ".join(f"{k}={v} ({v / total:.0%})" for k, v in sorted(calls.items())),
        "calls within repo (excl. library): " + ", ".join(f"{k}={v}" for k, v in sorted(internal.items())),
        f"parse errors: {len(errors)}" + (f" ({', '.join(errors[:5])})" if errors else ""),
        f"routes ({len(routes)}): " + "; ".join(routes[:10]) + (" ..." if len(routes) > 10 else ""),
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and save the code graph for a repository.")
    parser.add_argument("source", help="Git URL or local path")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    repo = load_repo(args.source, args.workspace)
    graph = build_graph(repo)
    out = graph_path(args.workspace, repo.root, repo.commit)
    save_graph(graph, out)
    print(summary(graph))
    print(f"saved:  {out}")


if __name__ == "__main__":
    main()
