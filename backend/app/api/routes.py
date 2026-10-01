"""HTTP API: load a repository, and ask questions with the agent's events streamed as Server-Sent Events."""

import json
import os
import queue
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.loop import Agent
from app.api.suggest import suggest_questions
from app.graph.build import DEFAULT_WORKSPACE
from app.graph.store import graph_path, latest_graph, save_graph
from app.ingest.loader import LoadError
from app.ingest.paths import PathError, RepoTooLarge
from app.llm.base import LLMError, LLMProvider
from app.llm.ollama import OllamaProvider
from app.toolfactory.factory import make_factory
from app.tools.repo import LoadedRepo

router = APIRouter(prefix="/api")

# One user, one repository at a time (plan assumption).
_state: dict = {"repo": None}
_runs: dict[str, threading.Event] = {}  # running question id -> cancel flag


def get_repo() -> LoadedRepo:
    if _state["repo"] is None:
        graph_file = latest_graph(DEFAULT_WORKSPACE)
        if graph_file is None:
            raise HTTPException(409, "no repository loaded; build a graph first")
        _state["repo"] = LoadedRepo.from_graph_file(graph_file)
    return _state["repo"]


def get_llm() -> LLMProvider:
    return OllamaProvider()


def get_factory(repo: LoadedRepo, llm: LLMProvider):
    return make_factory(repo, llm, DEFAULT_WORKSPACE)


def repo_summary(repo: LoadedRepo) -> dict:
    kinds: dict[str, int] = {}
    for _, kind in repo.graph.nodes(data="kind"):
        kinds[kind] = kinds.get(kind, 0) + 1
    return {"name": repo.root.name, "root": str(repo.root), "commit": repo.graph.graph.get("commit"),
            "files": len(repo.files), "nodes": repo.graph.number_of_nodes(), "edges": repo.graph.number_of_edges(),
            "kinds": kinds, "suggestions": suggest_questions(repo.graph)}


class RepoRequest(BaseModel):
    source: str


@router.get("/repo")
def current_repo() -> dict:
    return repo_summary(get_repo())


def allowed_roots() -> list[Path]:
    """Folders the UI may load local repositories from (the API has no login, so not the whole disk).

    Set AIEA_ALLOWED_ROOTS (separated by os.pathsep) to change; default: workspace/ and the Desktop.
    """
    configured = os.environ.get("AIEA_ALLOWED_ROOTS")
    roots = configured.split(os.pathsep) if configured else [str(DEFAULT_WORKSPACE), str(Path.home() / "Desktop")]
    return [Path(r).expanduser().resolve() for r in roots if r.strip()]


def check_local_source(source: str) -> None:
    local = Path(source).expanduser()
    if not local.is_dir():
        return  # a Git URL (or an invalid source, which the loader rejects)
    resolved = local.resolve()
    roots = allowed_roots()
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise HTTPException(403, "local repositories must be inside: " + ", ".join(map(str, roots))
                            + " (set AIEA_ALLOWED_ROOTS to change)")


@router.post("/repo")
def load_repository(body: RepoRequest) -> dict:
    """Clone (Git URL) or open (local path) a repository, build and save its graph, and switch to it."""
    source = body.source.strip()
    if not source:
        raise HTTPException(422, "source is empty")
    check_local_source(source)
    try:
        repo = LoadedRepo.build(source, DEFAULT_WORKSPACE)
    except (LoadError, RepoTooLarge, PathError) as err:
        raise HTTPException(400, str(err)) from err
    save_graph(repo.graph, graph_path(DEFAULT_WORKSPACE, repo.root, repo.graph.graph.get("commit")))
    _state["repo"] = repo
    return repo_summary(repo)


class AskRequest(BaseModel):
    question: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/ask")
def ask(body: AskRequest) -> StreamingResponse:
    if not body.question.strip():
        raise HTTPException(422, "question is empty")
    repo, llm = get_repo(), get_llm()
    events: queue.Queue = queue.Queue()
    done = object()
    run_id = uuid.uuid4().hex[:12]
    cancel = threading.Event()
    _runs[run_id] = cancel
    events.put(_sse("run", {"run_id": run_id}))

    def work() -> None:
        agent = Agent(repo, llm, on_event=lambda e: events.put(_sse(e.type, {**e.data, "t": e.t})),
                      tool_factory=get_factory(repo, llm), should_stop=cancel.is_set)
        try:
            result = agent.run(body.question)
            evidence = {k: v.to_dict() for k, v in result.evidence.items.items()}
            events.put(_sse("done", {"rounds": result.rounds, "seconds": result.seconds, "stopped": result.stopped,
                                     "gaps": [asdict(g) for g in result.gaps], "evidence": evidence}))
        except LLMError as err:
            events.put(_sse("error", {"message": str(err)}))
        except Exception as err:  # never leave the browser waiting on a dead stream
            events.put(_sse("error", {"message": f"internal error: {type(err).__name__}: {err}"}))
        finally:
            events.put(done)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        try:
            while (item := events.get()) is not done:
                yield item
        finally:
            # Also reached when the browser goes away mid-stream: stop the agent at its next step.
            cancel.set()
            _runs.pop(run_id, None)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/ask/{run_id}/cancel")
def cancel_run(run_id: str) -> dict:
    """Stop a running question at its next step (a model call already in progress finishes first)."""
    cancel = _runs.get(run_id)
    if cancel is None:
        raise HTTPException(404, "no running question with that id")
    cancel.set()
    return {"cancelled": run_id}
