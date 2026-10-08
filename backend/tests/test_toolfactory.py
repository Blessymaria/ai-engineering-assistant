import json
import os
import subprocess
from pathlib import Path

import pytest

from app.agent.actions import CapabilityGap
from app.agent.loop import Agent
from app.llm.base import LLMReply, ToolCallRequest
from app.runner.context import ToolContext
from app.runner.docker import DockerRunner, RunResult
from app.toolfactory.factory import ToolFactory, normalise_schema, wrap_body
from app.toolfactory.static_check import static_check
from app.tools.repo import LoadedRepo, ToolError

FIXTURE = Path(__file__).parent / "fixtures" / "shop"
GAP = CapabilityGap("git history of a function", "no tool reads git", "create_order")


class FakeLLM:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None, max_tokens=1024, json_schema=None):
        self.calls.append({"messages": messages, "json_schema": json_schema})
        return self.replies.pop(0)


class FakeRunner:
    """Stands in for Docker in unit tests: returns scripted results, never executes code."""

    def __init__(self, results):
        self.results = list(results)
        self.runs = []

    def run(self, code, args, handle_call):
        self.runs.append({"code": code, "args": args})
        return self.results.pop(0)


def ran(result):
    """A successful fake run that read repository data through ctx, as real tools must."""
    return RunResult(True, result, seconds=0.5, ctx_calls=[{"method": "git_log", "args": {"path": "svc.py"}}])


def spec(**overrides):
    base = {"name": "function_history", "description": "Last commits touching a function",
            "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}},
                             "required": ["symbol"]},
            "example_input": {"symbol": "create_order"},
            "code": 'hit = ctx.search_code(args["symbol"])["results"][0]\n'
                    'return {"path": hit["path"], "commits": ctx.git_log(hit["path"], 3)}'}
    base.update(overrides)
    return LLMReply(json.dumps(base), seconds=1.0)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


# --- static check -----------------------------------------------------------

def test_static_check_accepts_safe_code():
    source = wrap_body("import re\nfrom collections import Counter\nreturn {'n': len(ctx.list_nodes('function'))}")
    assert static_check(source) == []


@pytest.mark.parametrize("body, problem", [
    ("import os\nreturn {}", "import of 'os'"),
    ("from subprocess import run\nreturn {}", "import from 'subprocess'"),
    ("import socket\nreturn {}", "import of 'socket'"),
    ("return {'x': open('/etc/passwd').read()}", "'open'"),
    ("return {'x': eval('1')}", "'eval'"),
    ("exec('x=1')\nreturn {}", "'exec'"),
    ("return {'x': ().__class__.__bases__}", "double-underscore attribute"),
    ("return {'x': getattr(ctx, 'git_log')}", "'getattr'"),
    ("__builtins__['open']\nreturn {}", "double-underscore name"),
    ("from . import x\nreturn {}", "import from"),
    ("return {", "syntax error"),
])
def test_static_check_rejects(body, problem):
    assert any(problem in p for p in static_check(wrap_body(body)))


def test_static_check_requires_run_signature():
    assert any("def run(args, ctx)" in p for p in static_check("def run(a):\n    return {}\n"))


def test_wrap_body_accepts_body_or_full_function():
    assert wrap_body("  x = 1\n  return {'x': x}") == "def run(args, ctx):\n    x = 1\n    return {'x': x}\n"
    full = "def run(args, ctx):\n    return {}"
    assert wrap_body(full) == full + "\n"


def test_normalise_schema_shorthand_and_full():
    assert normalise_schema({"symbol": "string", "limit": "int"}) == {
        "type": "object", "properties": {"symbol": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["symbol", "limit"]}
    full = {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}
    assert normalise_schema(full) == full


# --- ToolContext --------------------------------------------------------------

@pytest.fixture(scope="module")
def git_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("gitrepo")
    env = {**os.environ, "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com",
           "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.com"}

    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)

    git("init", "-q")
    (root / "svc.py").write_text("def create():\n    return 1\n")
    git("add", "."), git("commit", "-q", "-m", "add create")
    (root / "svc.py").write_text("def create():\n    return 2\n")
    env["GIT_AUTHOR_NAME"] = "Grace"
    git("commit", "-q", "-am", "change create")
    return LoadedRepo.build(str(root), tmp_path_factory.mktemp("ws"))


def test_ctx_git_log_and_blame(git_repo):
    ctx = ToolContext(git_repo)
    log = ctx.handle("git_log", {"path": "svc.py"})
    assert [c["subject"] for c in log] == ["change create", "add create"]
    assert log[0]["author"] == "Grace"
    blame = ctx.handle("git_blame", {"path": "svc.py", "start": 1, "end": 2})
    assert [(b["line"], b["author"], b["summary"]) for b in blame] == [
        (1, "Ada", "add create"), (2, "Grace", "change create")]


@pytest.fixture(scope="module")
def history_repo(tmp_path_factory):
    """create() is changed by Grace; later Lin changes delete() in the same file and Max adds lines above create(),
    so the file's newest commits never touched create()."""
    root = tmp_path_factory.mktemp("historyrepo")
    env = {**os.environ, "GIT_COMMITTER_NAME": "ci", "GIT_COMMITTER_EMAIL": "ci@example.com"}

    def commit(author, message, text):
        (root / "svc.py").write_text(text)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", message], check=True, capture_output=True,
                       env={**env, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author.lower()}@example.com"})

    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
    commit("Ada", "add both", "def create():\n    return 1\n\n\ndef delete():\n    return 1\n")
    commit("Grace", "change create", "def create():\n    return 2\n\n\ndef delete():\n    return 1\n")
    commit("Lin", "change delete", "def create():\n    return 2\n\n\ndef delete():\n    return 3\n")
    commit("Max", "add header", "import os\nimport re\n\n\ndef create():\n    return 2\n\n\ndef delete():\n    return 3\n")
    return LoadedRepo.build(str(root), tmp_path_factory.mktemp("ws"))


def test_function_history_ignores_other_functions_in_the_same_file(history_repo):
    ctx = ToolContext(history_repo)
    create = next(n for n in ctx.handle("list_nodes", {"kind": "function"}) if n["name"] == "create")
    assert (create["line"], create["end"]) == (5, 6)  # moved down by Max's header
    # The whole-file log answers with commits that never touched create(): the evaluation's wrong answer
    assert [c["author"] for c in ctx.handle("git_log", {"path": "svc.py"})][:2] == ["Max", "Lin"]
    history = ctx.handle("git_log_lines", {"path": "svc.py", "start": create["line"], "end": create["end"]})
    assert [(c["author"], c["subject"]) for c in history] == [("Grace", "change create"), ("Ada", "add both")]
    assert history[0]["date"] and len(history[0]["commit"]) == 12


def test_git_log_lines_limits_and_errors(history_repo):
    ctx = ToolContext(history_repo)
    assert len(ctx.handle("git_log_lines", {"path": "svc.py", "start": 5, "end": 6, "limit": 1})) == 1
    assert ctx.handle("git_log_lines", {"path": "svc.py", "start": 9, "end": 500})[0]["author"] == "Lin"  # end clamped
    for args, message in [({"path": "svc.py", "start": 50, "end": 60}, "only 10 lines"),
                          ({"path": "svc.py", "start": 3, "end": 1}, "start <= end"),
                          ({"path": "../x.py", "start": 1, "end": 2}, "outside")]:
        with pytest.raises(ToolError, match=message):
            ctx.handle("git_log_lines", args)


def test_ctx_core_tools_and_list_nodes(repo):
    ctx = ToolContext(repo)
    assert ctx.handle("search_code", {"query": "create_order"})["results"][0]["id"] == \
        "shop.services.orders.create_order"
    funcs = ctx.handle("list_nodes", {"kind": "function"})
    assert {"id": "shop.services.orders.validate", "name": "validate", "path": "shop/services/orders.py",
            "line": 7, "end": 9} in funcs


@pytest.mark.parametrize("method, args, message", [
    ("run_shell", {}, "no method"),
    ("git_log", {"path": "../../etc"}, "outside"),
    ("git_log", {"path": "src/main.py"}, "no such file"),
    ("git_blame", {"path": "svc.py", "start": 5, "end": 2}, "start <= end"),
    ("list_nodes", {"kind": "secret"}, "must be one of"),
])
def test_ctx_rejects_bad_requests(git_repo, method, args, message):
    with pytest.raises(ToolError, match=message):
        ToolContext(git_repo).handle(method, args)


# --- factory ------------------------------------------------------------------

def test_factory_creates_and_registers_tool(repo, tmp_path):
    llm = FakeLLM([spec()])
    runner = FakeRunner([ran({"path": "shop/services/orders.py", "commits": []})])
    factory = ToolFactory(llm, runner, ToolContext(repo), tmp_path)
    result = factory.create(GAP)
    assert result.tool is not None and result.tool.name == "function_history"
    assert result.tool.parameters["properties"] == {"symbol": {"type": "string"}}
    assert runner.runs[0]["args"] == {"symbol": "create_order"}
    assert runner.runs[0]["code"].startswith("def run(args, ctx):\n")
    assert llm.calls[0]["json_schema"]["required"][-1] == "code"
    saved = json.loads((result.audit_dir / "validation.json").read_text())
    assert saved["created"] and (result.audit_dir / "tool.py").exists()


def test_prompt_lists_real_names_mentioned_first(repo, tmp_path):
    llm = FakeLLM([spec()])
    factory = ToolFactory(llm, FakeRunner([ran({"ok": 1})]), ToolContext(repo), tmp_path)
    names = factory.real_names(GAP)  # GAP.example_input is "create_order"
    assert names.splitlines()[0] == "- create_order (shop/services/orders.py:12-18)"
    factory.create(GAP)
    assert "- create_order (shop/services/orders.py:12-18)" in llm.calls[0]["messages"][0]["content"]


def test_factory_retries_once_with_errors(repo, tmp_path):
    llm = FakeLLM([spec(code="import os\nreturn {}"), spec()])
    runner = FakeRunner([ran({"ok": 1})])
    result = ToolFactory(llm, runner, ToolContext(repo), tmp_path).create(GAP)
    assert result.tool is not None and len(result.attempts) == 2
    assert "import of 'os'" in llm.calls[1]["messages"][-1]["content"]
    assert "create_order (shop/services/orders.py" in llm.calls[1]["messages"][-1]["content"]
    assert len(runner.runs) == 1  # the unsafe version was never run


def test_factory_gives_up_after_retry(repo, tmp_path):
    llm = FakeLLM([spec(), spec()])
    runner = FakeRunner([RunResult(False, error="RuntimeError: boom"), RunResult(True, [])])
    result = ToolFactory(llm, runner, ToolContext(repo), tmp_path).create(GAP)
    assert result.tool is None and len(result.attempts) == 2
    assert "non-empty dict" in result.errors[0]
    assert not (result.audit_dir / "tool.py").exists()
    assert json.loads((result.audit_dir / "validation.json").read_text())["created"] is False


def test_factory_rejects_tool_that_reads_nothing_from_ctx(repo, tmp_path):
    # Evaluation round 2, Q4: a generated tool returned a hard-coded count and was accepted.
    fabricated = spec(name="count_table_records",
                      input_schema={"type": "object", "properties": {"table_name": {"type": "string"}}},
                      example_input={"table_name": "articles"},
                      code='return {"table": args["table_name"], "count": 12345, "status": "success"}')
    runner = FakeRunner([RunResult(True, {"table": "articles", "count": 12345, "status": "success"}),
                         RunResult(True, {"table": "articles", "count": 12345, "status": "success"})])
    llm = FakeLLM([fabricated, fabricated])
    result = ToolFactory(llm, runner, ToolContext(repo), tmp_path).create(GAP)
    assert result.tool is None
    assert "made no ctx calls" in result.errors[0]
    assert "made no ctx calls" in llm.calls[1]["messages"][-1]["content"]


def test_factory_treats_error_result_as_failure(repo, tmp_path):
    runner = FakeRunner([ran({"error": "no such file"}), ran({"error": "still"})])
    result = ToolFactory(FakeLLM([spec(), spec()]), runner, ToolContext(repo), tmp_path).create(GAP)
    assert result.tool is None and "returned an error" in result.errors[0]


@pytest.mark.parametrize("reply, message", [
    (LLMReply('{"name": "x", "code": "ret'), "not valid JSON"),
    (spec(name="search_code"), "already used"),
    (spec(example_input={"other": 1}), "example_input does not match"),
])
def test_factory_rejects_bad_specs(repo, tmp_path, reply, message):
    result = ToolFactory(FakeLLM([reply, reply]), FakeRunner([]), ToolContext(repo), tmp_path).create(GAP)
    assert result.tool is None and any(message in e for e in result.errors)


def test_agent_uses_created_tool(repo, tmp_path):
    llm = FakeLLM([
        LLMReply("", [ToolCallRequest("report_capability_gap", {
            "missing_capability": "git history", "reason": "no git tool", "example_input": "create_order"})]),
        spec(),
        LLMReply("", [ToolCallRequest("function_history", {"symbol": "create_order"})]),
        LLMReply("Last changed by Grace [E1]."),
    ])
    runner = FakeRunner([ran({"commits": [{"author": "Grace"}]}),
                         ran({"commits": [{"author": "Grace"}]})])
    factory = ToolFactory(llm, runner, ToolContext(repo), tmp_path)
    result = Agent(repo, llm, tool_factory=factory).run("Who last changed create_order?")
    kinds = [e.type for e in result.events]
    assert "tool_generation_started" in kinds and "tool_created" in kinds
    assert result.evidence.items["E1"].tool == "function_history"
    assert result.answer == "Last changed by Grace [E1]." and result.citations["missing"] == []
    # calls: 0 agent, 1 factory, 2 agent right after creation (told about the new tool), 3 agent after using it
    assert "A new tool `function_history` was created" in llm.calls[2]["messages"][-1]["content"]


# --- real container (skipped where the runner image is not available) ----------

@pytest.fixture(scope="module")
def docker_runner():
    runner = DockerRunner(timeout=10)
    if not runner.available():
        pytest.skip("docker runner image not available")
    return runner


def test_container_runs_tool_with_ctx_calls(docker_runner):
    code = wrap_body('hits = ctx.search_code(args["q"])\nreturn {"n": len(hits["results"]), "echo": args["q"]}')
    calls = []

    def handle(method, args):
        calls.append((method, args))
        return {"results": [1, 2, 3]}

    result = docker_runner.run(code, {"q": "orders"}, handle)
    assert result.ok, result.error
    assert result.result == {"n": 3, "echo": "orders"}
    assert calls == [("search_code", {"query": "orders"})]


def test_container_function_history_tool_end_to_end(docker_runner, history_repo):
    """A tool written the way the prompt asks (find the symbol, then git_log_lines on its lines), run in the container."""
    code = wrap_body('node = [n for n in ctx.list_nodes("function") if n["name"] == args["name"]][0]\n'
                     'last = ctx.git_log_lines(node["path"], node["line"], node["end"], 1)[0]\n'
                     'return {"author": last["author"], "date": last["date"]}')
    result = docker_runner.run(code, {"name": "create"}, ToolContext(history_repo).handle)
    assert result.ok, result.error
    assert result.result["author"] == "Grace"
    assert [c["method"] for c in result.ctx_calls] == ["list_nodes", "git_log_lines"]


def test_container_has_no_network_and_readonly_fs(docker_runner):
    # These bypass the static check on purpose, to prove the container itself is the boundary.
    net = docker_runner.run("def run(args, ctx):\n    import socket\n"
                            "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n    return {'x': 1}\n",
                            {}, lambda m, a: None)
    assert not net.ok and "unreachable" in net.error.lower()
    fs = docker_runner.run("def run(args, ctx):\n    open('/pwned', 'w')\n    return {'x': 1}\n", {}, lambda m, a: None)
    assert not fs.ok and "read-only" in fs.error.lower()


def test_container_timeout_kills_the_tool(docker_runner):
    runner = DockerRunner(docker_runner.docker, timeout=3)
    result = runner.run("def run(args, ctx):\n    while True:\n        pass\n", {}, lambda m, a: None)
    assert not result.ok and "timed out" in result.error
    assert result.seconds < 15
