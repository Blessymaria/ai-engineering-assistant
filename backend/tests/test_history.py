import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.graph.store import graph_path, save_graph
from app.llm.base import LLMReply, ToolCallRequest
from app.main import app
from app.store.history import HistoryStore
from app.tools.repo import LoadedRepo

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


class FakeLLM:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, messages, tools=None, max_tokens=1024, json_schema=None):
        return self.replies.pop(0)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


@pytest.fixture
def api(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    monkeypatch.setattr(routes, "_state", {"repo": repo})
    monkeypatch.setattr(routes, "get_factory", lambda repo, llm: None)
    return TestClient(app)


def ask(api, monkeypatch, replies, question="Where is create_order?"):
    monkeypatch.setattr(routes, "get_llm", lambda: FakeLLM(replies))
    text = api.post("/api/ask", json={"question": question}).text
    return json.loads(text.strip().splitlines()[-1].removeprefix("data: "))  # the "done" event


# --- the store --------------------------------------------------------------

def test_store_save_list_get_delete(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    common = dict(repo_name="shop", repo_commit="abc", model="m", stopped="answer", rounds=1, seconds=2.5,
                  citations={"valid": 1}, diagram=None, events=[{"type": "answer", "data": {}}], evidence={})
    first = store.save(repo_root="/a", question="q1", answer="a1", **common)
    second = store.save(repo_root="/b", question="q2", answer="a2", **common)
    assert [r["id"] for r in store.list()] == [second, first]  # newest first
    assert [r["question"] for r in store.list(repo_root="/a")] == ["q1"]
    record = store.get(first)
    assert record["answer"] == "a1" and record["citations"] == {"valid": 1} and record["events"][0]["type"] == "answer"
    assert store.delete(first) and store.get(first) is None and not store.delete(first)


def test_store_survives_reopening(tmp_path):
    HistoryStore(tmp_path / "h.db").save(repo_name="r", repo_root="/r", repo_commit=None, model="m", question="q",
                                         answer="a", stopped="answer", rounds=0, seconds=0, citations={},
                                         diagram=None, events=[], evidence={})
    assert len(HistoryStore(tmp_path / "h.db").list()) == 1


# --- through the API ----------------------------------------------------------

def test_answered_question_is_saved_and_can_be_reopened(api, monkeypatch, repo):
    done = ask(api, monkeypatch, [LLMReply("", [ToolCallRequest("search_code", {"query": "create_order"})]),
                                  LLMReply("It is in orders.py [E1].")])
    conversation_id = done["history_id"]
    assert isinstance(conversation_id, int)

    listed = api.get("/api/history").json()
    assert [c["id"] for c in listed] == [conversation_id]
    assert listed[0]["question"] == "Where is create_order?" and listed[0]["repo_name"] == "shop"

    record = api.get(f"/api/history/{conversation_id}").json()
    assert record["answer"] == "It is in orders.py [E1]."
    assert record["evidence"]["E1"]["tool"] == "search_code"
    assert [e["type"] for e in record["events"]][0] == "started" and record["events"][-1]["type"] == "answer"
    assert record["repo_root"] == str(repo.root)


def test_history_lists_only_the_loaded_repository_unless_all(api, monkeypatch, tmp_path):
    routes.get_history().save(repo_name="other", repo_root="/elsewhere", repo_commit=None, model="m",
                              question="q", answer="a", stopped="answer", rounds=0, seconds=0, citations={},
                              diagram=None, events=[], evidence={})
    ask(api, monkeypatch, [LLMReply("", [ToolCallRequest("list_files", {})]), LLMReply("Files [E1].")])
    assert len(api.get("/api/history").json()) == 1
    assert len(api.get("/api/history?all=true").json()) == 2


def test_delete_and_missing_conversation(api, monkeypatch):
    done = ask(api, monkeypatch, [LLMReply("", [ToolCallRequest("list_files", {})]), LLMReply("Files [E1].")])
    assert api.delete(f"/api/history/{done['history_id']}").json() == {"deleted": done["history_id"]}
    assert api.get(f"/api/history/{done['history_id']}").status_code == 404
    assert api.delete("/api/history/999").status_code == 404


# --- remembering the repository ---------------------------------------------------

def test_restart_reopens_the_last_loaded_repository(tmp_path, monkeypatch, repo):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    older = graph_path(tmp_path, repo.root, "aaa")
    newer = graph_path(tmp_path, Path("/x/other"), "bbb")
    save_graph(repo.graph, older)
    save_graph(repo.graph, newer)  # the newest file, but not the one in use
    routes.remember_graph(older)
    monkeypatch.setattr(routes, "_state", {"repo": None})  # as after a restart
    routes.get_repo()
    assert routes.remembered_graph() == older


def test_remembered_graph_falls_back_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    routes.remember_graph(tmp_path / "graphs" / "gone.json")
    assert routes.remembered_graph() is None
