"""Run the evaluation questions through the agent and save every run for hand-checking.

Usage (from backend/): .venv/Scripts/python ../eval/run_eval.py [--only Q3,Q8] [--graph FILE]
Writes eval/results/<id>-run<n>.json (answer, citations, diagram, every event, full evidence)
and eval/results/summary.json. Judging correctness is done by hand in eval/RESULTS.md.
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL.parent / "backend"))

from app.agent.loop import Agent  # noqa: E402
from app.graph.build import DEFAULT_WORKSPACE  # noqa: E402
from app.graph.store import latest_graph  # noqa: E402
from app.llm.ollama import OllamaProvider  # noqa: E402
from app.toolfactory.factory import make_factory  # noqa: E402
from app.tools.repo import LoadedRepo  # noqa: E402

RESULTS = EVAL / "results"


def git_head(path: Path) -> str:
    out = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    return out.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated question ids")
    parser.add_argument("--graph", type=Path)
    opts = parser.parse_args()

    questions = json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))
    if opts.only:
        wanted = set(opts.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    repo = LoadedRepo.from_graph_file(opts.graph or latest_graph(DEFAULT_WORKSPACE))
    llm = OllamaProvider()
    RESULTS.mkdir(parents=True, exist_ok=True)
    context = {
        "model": llm.name, "machine": platform.processor() or platform.machine(), "os": platform.platform(),
        "assistant_commit": git_head(EVAL.parent), "demo_repo": repo.root.name, "demo_commit": git_head(repo.root),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    summary = {"context": context, "runs": []}

    for q in questions:
        for run in range(1, q.get("runs", 1) + 1):
            print(f"== {q['id']} run {run}: {q['question']}", flush=True)
            factory = make_factory(repo, llm, DEFAULT_WORKSPACE)  # fresh per run: no tools carried over
            agent = Agent(repo, llm, tool_factory=factory)
            result = agent.run(q["question"])
            created = [e.data for e in result.events if e.type == "tool_created"]
            record = {
                "id": q["id"], "run": run, "question": q["question"], "expected": q["expected"],
                "answer": result.answer, "citations": result.citations, "diagram": result.diagram,
                "rounds": result.rounds, "seconds": result.seconds, "stopped": result.stopped,
                "gaps": [asdict(g) for g in result.gaps],
                "tools_created": [{"name": c["name"], "attempts": c["attempts"], "seconds": c["seconds"]}
                                  for c in created],
                "tool_failures": [e.data for e in result.events if e.type == "tool_failed"],
                "steps": [{"type": e.type, **{k: v for k, v in e.data.items() if k not in ("code", "text")}}
                          for e in result.events],
                "evidence": {k: v.to_dict() for k, v in result.evidence.items.items()},
            }
            name = f"{q['id']}-run{run}.json"
            (RESULTS / name).write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            summary["runs"].append({k: record[k] for k in ("id", "run", "rounds", "seconds", "stopped",
                                                           "citations", "tools_created")} | {"file": name})
            (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"   {result.rounds} rounds, {result.seconds}s, citations {result.citations['valid']}/"
                  f"{result.citations['total']}, tools created: {[c['name'] for c in created]}", flush=True)
    print("done")


if __name__ == "__main__":
    main()
