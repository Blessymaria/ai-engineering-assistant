"""Ask the agent a question from the command line, showing each step live.

Usage: python -m app.agent "What happens when POST /articles is called?" [--graph FILE] [--max-rounds N]
"""

import argparse
import sys
from pathlib import Path

from app.agent.loop import MAX_ROUNDS, Agent, Event
from app.graph.build import DEFAULT_WORKSPACE
from app.graph.store import latest_graph
from app.llm.base import LLMError
from app.llm.ollama import OllamaProvider
from app.toolfactory.factory import make_factory
from app.tools.repo import LoadedRepo


def show(event: Event) -> None:
    d = event.data
    if event.type == "started":
        print(f"Question: {d['question']}\nModel: {d['model']}, up to {d['max_rounds']} tool rounds\n")
    elif event.type == "llm_reply":
        print(f"  model replied in {d['seconds']}s ({d['tokens']} tokens)", flush=True)
    elif event.type == "tool_called":
        args = ", ".join(f"{k}={v!r}" for k, v in d["args"].items())
        print(f"[{d['round']}] {d['tool']}({args})", flush=True)
    elif event.type == "tool_result":
        print(f"    -> {d['evidence_id']}: {d['summary']} ({d['ms']} ms)", flush=True)
    elif event.type == "tool_error":
        print(f"    -> error: {d['error']}", flush=True)
    elif event.type == "gap_detected":
        print(f"[{d['round']}] GAP: {d['missing_capability']} - {d['reason']}", flush=True)
    elif event.type == "invalid_action":
        print(f"[{d['round']}] invalid action: {d['error']}", flush=True)
    elif event.type == "tool_generation_started":
        print(f"    creating a tool for: {d['missing_capability']} ...", flush=True)
    elif event.type == "tool_created":
        print(f"    TOOL CREATED: {d['name']}({', '.join(d['parameters']['properties'])}) - {d['description']}\n"
              f"    tested on {d['test_input']} in {d['seconds']}s after {d['attempts']} attempt(s); "
              f"saved to {d['audit_dir']}", flush=True)
        print("    " + d["code"].replace("\n", "\n    "), flush=True)
    elif event.type == "tool_failed":
        print(f"    tool creation failed after {d['attempts']} attempt(s): {d['errors']}", flush=True)
    elif event.type == "limit_reached":
        print(f"Tool limit reached after {d['rounds']} rounds; asking for a final answer", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the agent a question about the loaded repository.")
    parser.add_argument("question")
    parser.add_argument("--graph", type=Path, help="graph file (default: newest in workspace/graphs)")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    parser.add_argument("--no-tool-creation", action="store_true", help="report gaps without creating tools")
    opts = parser.parse_args()

    graph_file = opts.graph or latest_graph(DEFAULT_WORKSPACE)
    if graph_file is None:
        sys.exit("no graph found; build one with: python -m app.graph.build <git-url-or-path>")
    repo, llm = LoadedRepo.from_graph_file(graph_file), OllamaProvider()
    factory = None if opts.no_tool_creation else make_factory(repo, llm, DEFAULT_WORKSPACE)
    if factory is None and not opts.no_tool_creation:
        print("Note: container runner not available, so capability gaps cannot create tools.\n")
    agent = Agent(repo, llm, opts.max_rounds, on_event=show, tool_factory=factory)
    try:
        result = agent.run(opts.question)
    except LLMError as err:
        sys.exit(f"error: {err}")
    c = result.citations
    print(f"\n{'=' * 70}\n{result.answer}\n{'=' * 70}")
    print(f"{result.rounds} tool rounds, {result.seconds}s, stopped by {result.stopped}; "
          f"citations valid {c['valid']}/{c['total']}" + (f", missing {c['missing']}" if c["missing"] else ""))


if __name__ == "__main__":
    main()
