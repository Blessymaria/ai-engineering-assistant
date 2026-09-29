"""Run a core tool by hand against a saved graph.

Usage: python -m app.tools <tool> '<json args>' [--graph FILE]
Example: python -m app.tools search_code '{"query": "POST /articles"}'
"""

import argparse
import json
import sys
from pathlib import Path

from app.graph.build import DEFAULT_WORKSPACE
from app.tools.registry import CORE_TOOLS, run_tool
from app.tools.repo import LoadedRepo, ToolError


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a core tool against a saved code graph.")
    parser.add_argument("tool", choices=sorted(CORE_TOOLS))
    parser.add_argument("args", nargs="?", default="{}", help="JSON object of arguments")
    parser.add_argument("--graph", type=Path, help="graph file (default: newest in workspace/graphs)")
    opts = parser.parse_args()

    graph_file = opts.graph or max((DEFAULT_WORKSPACE / "graphs").glob("*.json"), key=lambda p: p.stat().st_mtime,
                                   default=None)
    if graph_file is None:
        sys.exit("no graph found; build one with: python -m app.graph.build <git-url-or-path>")
    repo = LoadedRepo.from_graph_file(graph_file)
    try:
        result = run_tool(repo, opts.tool, json.loads(opts.args))
    except (ToolError, json.JSONDecodeError) as err:
        sys.exit(f"error: {err}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
