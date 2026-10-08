from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.api.intro import facts_intro, repo_facts, repo_intro
from app.llm.base import LLMError, LLMReply
from app.main import app
from app.tools.repo import LoadedRepo

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


class FakeLLM:
    name = "fake"

    def __init__(self, reply="Shop is a small FastAPI order service.", fail=False):
        self.reply, self.fail, self.prompts = reply, fail, []

    def chat(self, messages, tools=None, max_tokens=1024, json_schema=None):
        self.prompts.append(messages[-1]["content"])
        if self.fail:
            raise LLMError("ollama is not running")
        return LLMReply(self.reply)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


def test_facts_come_from_the_graph_and_readme(repo):
    facts = repo_facts(repo)
    assert facts["name"] == "shop" and facts["routes"] > 0 and facts["python_files"] > 0
    assert "fastapi" in facts["main_libraries"]
    assert all(lib not in facts["main_libraries"] for lib in ("os", "typing", "json"))  # standard library left out
    assert facts["readme_start"]


def test_intro_from_the_model_is_cached(repo, tmp_path):
    llm = FakeLLM("  Shop is a small\n FastAPI order service.  ")
    first = repo_intro(repo, llm, tmp_path)
    assert first == {"text": "Shop is a small FastAPI order service.", "source": "model", "cached": False}
    assert "fastapi" in llm.prompts[0]  # the facts are in the prompt
    second = repo_intro(repo, FakeLLM("something else"), tmp_path)
    assert second["text"] == first["text"] and second["cached"]


def test_falls_back_to_facts_when_the_model_fails(repo, tmp_path):
    result = repo_intro(repo, FakeLLM(fail=True), tmp_path)
    assert result["source"] == "facts" and result["text"] == facts_intro(repo_facts(repo))
    assert "shop is a Python project" in result["text"]
    # not cached, so the model is tried again once it is back
    assert repo_intro(repo, FakeLLM("Back again."), tmp_path)["source"] == "model"


def test_empty_model_reply_falls_back(repo, tmp_path):
    assert repo_intro(repo, FakeLLM("   "), tmp_path)["source"] == "facts"


def test_intro_endpoint(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    monkeypatch.setattr(routes, "_state", {"repo": repo})
    monkeypatch.setattr(routes, "get_llm", lambda: FakeLLM())
    body = TestClient(app).get("/api/repo/intro").json()
    assert body["text"] == "Shop is a small FastAPI order service." and body["source"] == "model"
