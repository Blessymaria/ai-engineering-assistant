import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent import evidence as evidence_mod
from app.agent.actions import CapabilityGap, FinalAnswer, Invalid, ToolCall, parse_reply
from app.agent.evidence import EvidenceStore, check_citations, compact
from app.agent.loop import Agent
from app.api import routes
from app.llm.base import LLMReply, ToolCallRequest
from app.main import app
from app.tools.registry import run_tool
from app.tools.repo import LoadedRepo

FIXTURE = Path(__file__).parent / "fixtures" / "shop"
TOOLS = {"search_code", "query_graph", "read_file", "list_files"}


class FakeLLM:
    """Returns scripted replies and records what it was sent."""
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None, max_tokens=1024, json_schema=None):
        self.calls.append({"messages": messages, "tools": tools, "json_schema": json_schema})
        return self.replies.pop(0)


def call(name, **args):
    return LLMReply("", [ToolCallRequest(name, args)], tokens=10, seconds=0.1)


def text(content):
    return LLMReply(content, tokens=20, seconds=0.1)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


# --- parse_reply ------------------------------------------------------------

def test_parse_tool_call():
    action = parse_reply(call("search_code", query="x"), TOOLS)
    assert action == ToolCall("search_code", {"query": "x"})


def test_parse_final_answer_and_empty():
    assert parse_reply(text(" The answer. "), TOOLS) == FinalAnswer("The answer.")
    assert isinstance(parse_reply(text("  "), TOOLS), Invalid)


def test_parse_only_first_of_several_calls():
    reply = LLMReply("", [ToolCallRequest("search_code", {"query": "a"}), ToolCallRequest("list_files", {})])
    action = parse_reply(reply, TOOLS)
    assert action.name == "search_code" and "first of 2" in action.note


def test_parse_unknown_tool():
    action = parse_reply(call("run_shell", cmd="ls"), TOOLS)
    assert isinstance(action, Invalid) and "unknown tool" in action.error


@pytest.mark.parametrize("content", [
    '{"name": "search_code", "arguments": {"query": "orders"}}',
    '```json\n{"tool": "search_code", "parameters": {"query": "orders"}}\n```',
])
def test_parse_tool_call_written_as_text(content):
    assert parse_reply(text(content), TOOLS) == ToolCall("search_code", {"query": "orders"})


def test_parse_capability_gap():
    reply = call("report_capability_gap", missing_capability="git history", reason="no git tool",
                 example_input="create_order")
    assert parse_reply(reply, TOOLS) == CapabilityGap("git history", "no git tool", "create_order")
    incomplete = call("report_capability_gap", missing_capability="git history")
    assert "needs" in parse_reply(incomplete, TOOLS).error


def test_ollama_sets_context_window_and_caps(monkeypatch):
    from app.llm.ollama import DEFAULT_NUM_CTX, OllamaProvider
    sent = {}

    def fake_post(self, body):
        sent.update(body)
        return {"message": {"content": "hi"}, "eval_count": 1, "prompt_eval_count": 50}

    monkeypatch.setattr(OllamaProvider, "_post", fake_post)
    reply = OllamaProvider(model="m").chat([{"role": "user", "content": "q"}], max_tokens=64)
    assert sent["options"] == {"temperature": 0, "num_predict": 64, "num_ctx": DEFAULT_NUM_CTX}
    assert reply.prompt_tokens == 50


# --- evidence ---------------------------------------------------------------

def test_compact_graph_result_is_short_and_keeps_status(repo):
    result = run_tool(repo, "query_graph", {"node": "create_order", "relation": "callees"})
    out = compact("query_graph", result)
    assert "[ambiguous] shop.db.repo.OrderRepo.save" in out
    assert "[unresolved] unresolved:notifier" in out
    assert "Note:" in out
    # callees: the call site is in the start node's file
    assert "shop.services.orders.validate defined at shop/services/orders.py:7; call at shop/services/orders.py:14" in out


def test_compact_callers_give_call_site_in_the_callers_file(repo):
    out = compact("query_graph", run_tool(repo, "query_graph", {"node": "create_order", "relation": "callers"}))
    assert "shop.api.routes.post_order defined at shop/api/routes.py:12; call at shop/api/routes.py:14" in out


def test_compact_read_file_caps_lines(repo, monkeypatch):
    monkeypatch.setattr(evidence_mod, "MAX_FILE_LINES", 3)
    out = compact("read_file", run_tool(repo, "read_file", {"path": "shop/db/repo.py"}))
    assert out.count("| ") == 3 and "narrower range" in out


def test_citation_check():
    store = EvidenceStore()
    store.add("list_files", {}, {"path": ".", "entries": []})
    store.add("list_files", {}, {"path": ".", "entries": []})
    result = check_citations("Saved in [E1, a.py:3] and [E2][E7]. Also E9 without brackets.", store)
    assert result == {"cited": ["E1", "E2", "E7"], "missing": ["E7"], "valid": 2, "total": 3}


# --- loop -------------------------------------------------------------------

def test_agent_multi_step_answer(repo):
    llm = FakeLLM([
        call("search_code", query="create_order"),
        call("query_graph", node="shop.services.orders.create_order", relation="callees"),
        text("`create_order` validates first [E1, shop/services/orders.py:12] then saves [E2]."),
    ])
    events = []
    result = Agent(repo, llm, on_event=events.append).run("What does create_order do?")
    assert result.stopped == "answer" and result.rounds == 2
    assert list(result.evidence.items) == ["E1", "E2"]
    assert result.citations["missing"] == [] and result.citations["valid"] == 2
    kinds = [e.type for e in events]
    assert kinds[0] == "started" and kinds[-1] == "answer"
    assert kinds.count("tool_result") == 2
    # The model saw the compact E1 result on its next turn
    last_messages = llm.calls[2]["messages"]
    assert any(m["role"] == "tool" and m["content"].startswith("[E1]") for m in last_messages)


def test_tool_errors_go_back_to_the_model(repo):
    llm = FakeLLM([
        call("read_file", path="../../secret"),
        call("list_files"),
        text("Done [E1]."),
    ])
    result = Agent(repo, llm).run("q")
    errors = [e for e in result.events if e.type == "tool_error"]
    assert len(errors) == 1 and "outside" in errors[0].data["error"]
    assert result.rounds == 2
    assert any(m["content"].startswith("Error:") for m in llm.calls[1]["messages"] if m["role"] == "tool")


def test_answer_without_tools_is_nudged_once(repo):
    llm = FakeLLM([text("I think it saves orders."), call("list_files"), text("It saves orders [E1].")])
    result = Agent(repo, llm).run("q")
    assert [e.type for e in result.events].count("invalid_action") == 1
    assert result.answer == "It saves orders [E1]."


def test_gap_is_recorded_and_the_loop_continues(repo):
    llm = FakeLLM([
        call("report_capability_gap", missing_capability="git history", reason="no git tool",
             example_input="create_order"),
        text("Unresolved: no git history is available."),
    ])
    result = Agent(repo, llm).run("Who last changed create_order?")
    assert result.gaps == [CapabilityGap("git history", "no git tool", "create_order")]
    assert any(e.type == "gap_detected" for e in result.events)
    tool_msgs = [m for m in llm.calls[1]["messages"] if m["role"] == "tool"]
    assert "No new tool" in tool_msgs[-1]["content"]


def test_round_limit_forces_an_answer_without_tools(repo):
    llm = FakeLLM([call("list_files")] * 3 + [text("Partial answer [E3]; the rest is unresolved.")])
    result = Agent(repo, llm, max_rounds=3).run("q")
    assert result.stopped == "limit" and result.rounds == 3
    assert llm.calls[-1]["tools"] is None
    assert "tool limit" in llm.calls[-1]["messages"][-1]["content"]
    assert any(e.type == "limit_reached" for e in result.events)


def test_uncited_answer_is_sent_back_once(repo):
    llm = FakeLLM([call("list_files"), text("The code is in shop/."), text("The code is in shop/ [E1].")])
    result = Agent(repo, llm).run("Where is the code?")
    assert result.answer == "The code is in shop/ [E1]."
    assert result.citations["valid"] == 1 and result.rounds == 1  # the rewrite is not a tool round
    assert "cites no evidence" in llm.calls[2]["messages"][-1]["content"]


def test_answer_citing_unknown_ids_is_sent_back_once_then_accepted(repo):
    llm = FakeLLM([call("list_files"), text("See [E9]."), text("Still [E9].")])
    result = Agent(repo, llm).run("q")
    assert result.answer == "Still [E9]." and result.citations["missing"] == ["E9"]
    assert "does not exist: ['E9']" in llm.calls[2]["messages"][-1]["content"]


def test_unconfirmed_calls_are_listed_under_the_answer(repo):
    llm = FakeLLM([call("query_graph", node="create_order", relation="callees"), text("It saves [E1].")])
    result = Agent(repo, llm).run("What does create_order do?")
    assert result.answer.startswith("It saves [E1].")
    assert "**Not statically confirmed**" in result.answer
    assert "`create_order` calls `shop.db.repo.OrderRepo.save` at `shop/services/orders.py:16`: ambiguous [E1]" \
        in result.answer
    assert "`create_order` calls `notifier` at `shop/services/orders.py:17`: unresolved [E1]" in result.answer
    assert result.citations == {"cited": ["E1"], "missing": [], "valid": 1, "total": 1}  # model text only


def test_no_note_when_all_calls_are_confirmed(repo):
    llm = FakeLLM([call("query_graph", node="shop.db.repo.BaseRepo.get", relation="callees"), text("Fetches [E1].")])
    assert Agent(repo, llm).run("q").answer == "Fetches [E1]."


def test_agent_stops_between_steps_when_cancelled(repo):
    llm = FakeLLM([call("list_files"), call("list_files"), text("never reached")])
    checks = iter([False, True])  # allow the first step, then cancel
    result = Agent(repo, llm, should_stop=lambda: next(checks)).run("q")
    assert result.stopped == "cancelled" and result.rounds == 1 and result.answer == ""
    assert result.events[-1].type == "cancelled"
    assert len(llm.calls) == 1  # no further model calls after cancelling


def test_cancel_endpoint(monkeypatch):
    import threading
    flag = threading.Event()
    monkeypatch.setattr(routes, "_runs", {"abc123": flag})
    client = TestClient(app)
    assert client.post("/api/ask/abc123/cancel").json() == {"cancelled": "abc123"}
    assert flag.is_set()
    assert client.post("/api/ask/nope/cancel").status_code == 404


def test_old_results_shrink_to_summaries(repo):
    llm = FakeLLM([call("list_files")] * 5 + [text("ok [E5]")])
    Agent(repo, llm).run("q")
    tool_msgs = [m["content"] for m in llm.calls[-1]["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 5
    assert all("(older result)" in m for m in tool_msgs[:2])
    assert not any("(older result)" in m for m in tool_msgs[2:])


# --- API --------------------------------------------------------------------

def test_ask_streams_events(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)  # history.db goes here, not the real workspace
    llm = FakeLLM([call("search_code", query="create_order"), text("It is in orders.py [E1].")])
    monkeypatch.setattr(routes, "_state", {"repo": repo})
    monkeypatch.setattr(routes, "get_llm", lambda: llm)
    monkeypatch.setattr(routes, "get_factory", lambda repo, llm: None)
    response = TestClient(app).post("/api/ask", json={"question": "Where is create_order?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line.removeprefix("event: ") for line in response.text.splitlines() if line.startswith("event: ")]
    assert events[:2] == ["run", "started"] and events[-1] == "done"
    assert "answer" in events and "tool_result" in events
    done = json.loads(response.text.strip().splitlines()[-1].removeprefix("data: "))
    assert done["evidence"]["E1"]["tool"] == "search_code"


def test_ask_rejects_empty_question(monkeypatch, repo):
    monkeypatch.setattr(routes, "_state", {"repo": repo})
    assert TestClient(app).post("/api/ask", json={"question": " "}).status_code == 422
