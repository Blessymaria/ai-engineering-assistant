"""HTTP API: ask a question and stream the agent's events as Server-Sent Events."""

import json
import queue
import threading
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.loop import Agent
from app.graph.build import DEFAULT_WORKSPACE
from app.graph.store import latest_graph
from app.llm.base import LLMError, LLMProvider
from app.llm.ollama import OllamaProvider
from app.tools.repo import LoadedRepo

router = APIRouter(prefix="/api")

# One user, one repository at a time (plan assumption).
_state: dict = {"repo": None}


def get_repo() -> LoadedRepo:
    if _state["repo"] is None:
        graph_file = latest_graph(DEFAULT_WORKSPACE)
        if graph_file is None:
            raise HTTPException(409, "no repository loaded; build a graph first")
        _state["repo"] = LoadedRepo.from_graph_file(graph_file)
    return _state["repo"]


def get_llm() -> LLMProvider:
    return OllamaProvider()


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

    def work() -> None:
        agent = Agent(repo, llm, on_event=lambda e: events.put(_sse(e.type, {**e.data, "t": e.t})))
        try:
            result = agent.run(body.question)
            evidence = {k: v.to_dict() for k, v in result.evidence.items.items()}
            events.put(_sse("done", {"rounds": result.rounds, "seconds": result.seconds, "stopped": result.stopped,
                                     "gaps": [asdict(g) for g in result.gaps], "evidence": evidence}))
        except LLMError as err:
            events.put(_sse("error", {"message": str(err)}))
        finally:
            events.put(done)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not done:
            yield item

    return StreamingResponse(stream(), media_type="text/event-stream")
