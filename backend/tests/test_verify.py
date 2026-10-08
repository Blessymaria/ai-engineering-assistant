from pathlib import Path

import pytest

from app.agent.evidence import EvidenceStore
from app.agent.loop import Agent
from app.agent.verify import check_answer
from app.llm.base import LLMReply, ToolCallRequest
from app.tools.registry import run_tool
from app.tools.repo import LoadedRepo

FIXTURE = Path(__file__).parent / "fixtures" / "shop"
ORDERS = "shop/services/orders.py"  # 22 lines; create_order is 12-18, its repo.save() call at 16


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


def store_with(repo, *calls):
    store = EvidenceStore()
    for tool, args in calls:
        store.add(tool, args, run_tool(repo, tool, args))
    return store


def test_citations_inside_the_evidence_pass(repo):
    store = store_with(repo, ("read_file", {"path": ORDERS, "start": 10, "end": 20}),
                       ("query_graph", {"node": "create_order", "relation": "callees"}))
    answer = (f"It validates first [E1, {ORDERS}:14], then saves [E2, {ORDERS}:16] "
              f"(defined in `{ORDERS}` and `shop/db/repo.py`, under `shop/services/`).")
    assert check_answer(answer, store, repo) == []


def test_citation_outside_what_the_evidence_showed(repo):
    store = store_with(repo, ("read_file", {"path": ORDERS, "start": 1, "end": 8}))
    problems = check_answer(f"It saves the order [E1, {ORDERS}:16].", store, repo)
    assert problems == [f"[E1, {ORDERS}:16]: E1 did not show {ORDERS}:16; cite the evidence that contains those lines"]


def test_citation_of_a_missing_file_or_line(repo):
    store = store_with(repo, ("read_file", {"path": ORDERS}))
    problems = check_answer(f"See [E1, shop/models.py:3] and [E1, {ORDERS}:90-95].", store, repo)
    assert "cites shop/models.py, which is not a file in the repository" in problems[0]
    assert "but the file has 22 lines" in problems[1]


def test_graph_evidence_covers_call_lines_and_function_bodies(repo):
    store = store_with(repo, ("query_graph", {"node": "create_order", "relation": "callees"}))
    # call_line 16 is in the caller's file; the callee's own definition lines are covered too
    assert check_answer(f"[E1, {ORDERS}:16] [E1, shop/db/repo.py:{repo.graph.nodes['shop.db.repo.OrderRepo.save']['start']}]",
                        store, repo) == []


def test_invented_paths_are_reported(repo):
    """The evaluation's structure answer kept naming an app/db/models/ folder that does not exist."""
    store = store_with(repo, ("list_files", {}))
    answer = ("Models live in `shop/models/` and `shop/db/schema.py`; services are in `shop/services/` and "
              "`orders.py`. Routes like GET /orders/{id} and https://example.com/a/b are not paths.")
    assert check_answer(answer, store, repo) == [
        "names `shop/models/`, which does not exist in the repository",
        "names `shop/db/schema.py`, which does not exist in the repository"]


def test_folder_named_relative_to_its_parent_is_not_reported(repo):
    """Found in evaluation round 7: "`shop/` contains `services/` and `api/`" was wrongly reported."""
    store = store_with(repo, ("list_files", {}))
    answer = "`shop/` contains `services/`, `api/` and `db/`; but `shop/db/models/` and `widgets/` do not exist."
    assert check_answer(answer, store, repo) == [
        "names `shop/db/models/`, which does not exist in the repository",
        "names `widgets/`, which does not exist in the repository"]


class FakeLLM:
    name = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, tools=None, max_tokens=1024, json_schema=None):
        self.calls.append(messages)
        return self.replies.pop(0)


def test_agent_sends_a_wrong_location_back_once_then_reports_what_remains(repo):
    llm = FakeLLM([LLMReply("", [ToolCallRequest("read_file", {"path": ORDERS, "start": 1, "end": 8})]),
                   LLMReply(f"It saves the order [E1, {ORDERS}:16] in `shop/models/`."),
                   LLMReply(f"It saves the order [E1, {ORDERS}:16].")])
    result = Agent(repo, llm).run("What does create_order do?")
    rewrite_request = llm.calls[2][-1]["content"]
    assert "did not show shop/services/orders.py:16" in rewrite_request and "`shop/models/`" in rewrite_request
    assert len(llm.calls) == 3  # one rewrite only, no loop
    assert result.citations["problems"] == [
        f"[E1, {ORDERS}:16]: E1 did not show {ORDERS}:16; cite the evidence that contains those lines"]


def test_agent_accepts_a_correct_answer_without_a_rewrite(repo):
    llm = FakeLLM([LLMReply("", [ToolCallRequest("read_file", {"path": ORDERS})]),
                   LLMReply(f"It saves the order [E1, {ORDERS}:16].")])
    result = Agent(repo, llm).run("What does create_order do?")
    assert len(llm.calls) == 2 and result.citations["problems"] == []
