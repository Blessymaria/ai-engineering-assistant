"""Phase 1 model selection test: speed and single tool calls via Ollama.

Usage: py -3.13 eval/model_test.py [model ...]
Writes eval/results/model_test.json and prints a summary table.
Uses only the standard library so it runs before the backend exists.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434"
MODELS = sys.argv[1:] or ["qwen3:4b", "gemma4:e4b"]
TIMEOUT = 300
RESULTS = Path(__file__).parent / "results" / "model_test.json"

SYSTEM = (
    "You answer questions about a Python repository by calling tools. "
    "Call exactly one tool per reply. If no tool can get the needed information, "
    "call report_capability_gap instead of guessing."
)


def tool(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


STR = {"type": "string"}
INT = {"type": "integer"}

TOOLS = [
    tool("search_code", "Ranked text search over symbols, paths, docstrings, routes, source and docs.",
         {"query": STR}, ["query"]),
    tool("query_graph", "Related nodes of a code element: callers, callees, imports, contents, route handlers.",
         {"node": STR, "relation": {"type": "string", "enum": ["callers", "callees", "imports", "contains", "handlers"]},
          "depth": INT}, ["node", "relation"]),
    tool("read_file", "Source lines of a file with line numbers.",
         {"path": STR, "start": INT, "end": INT}, ["path"]),
    tool("list_files", "Directory structure under a path.", {"path": STR}, ["path"]),
    tool("report_capability_gap", "Report that no tool can provide what is needed.",
         {"missing_capability": STR, "reason": STR, "example_input": STR},
         ["missing_capability", "reason", "example_input"]),
]

# (question, expected tool, required arg check)
TOOL_CASES = [
    ("Where is the function create_article defined?", "search_code", lambda a: "create_article" in a.get("query", "")),
    ("Which functions call create_article? Its node id is app.services.articles.create_article.",
     "query_graph", lambda a: a.get("relation") == "callers" and "create_article" in a.get("node", "")),
    ("Show me lines 10 to 40 of app/api/routes/articles.py.",
     "read_file", lambda a: a.get("path", "").endswith("articles.py") and a.get("start") == 10),
    ("What files are in the app/db directory?", "list_files", lambda a: "app/db" in a.get("path", "")),
    ("Which route handles POST /articles?", "search_code", lambda a: "article" in a.get("query", "").lower()),
    ("What does the module app.db.repositories.users import? Node id: app.db.repositories.users.",
     "query_graph", lambda a: a.get("relation") == "imports"),
    ("When was create_article last changed in git, and by whom?", "report_capability_gap", lambda a: bool(a.get("reason"))),
    ("List every function in the repository that is never called anywhere, in one step.",
     "report_capability_gap", lambda a: bool(a.get("reason"))),
]

TOOL_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "input_schema": {"type": "object"},
        "example_input": {"type": "object"},
        "code": {"type": "string"},
    },
    "required": ["name", "description", "input_schema", "example_input", "code"],
}

EXAMPLE_TOOL = '''def run(args, ctx):
    hits = ctx.search_code(args["query"])
    return {"count": len(hits), "files": sorted({h["path"] for h in hits})}'''

SPEC_PROMPT = (
    "Write a Python tool. Only fill in the body of run(args, ctx). ctx methods: search_code(query), "
    "query_graph(node, relation, depth), read_file(path, start, end), list_files(path), list_nodes(kind), "
    "git_log(path, limit), git_blame(path, start, end). Allowed imports: re, json, collections, itertools, math.\n"
    "Example tool:\n" + EXAMPLE_TOOL + "\n\nNeeded capability: TASK\n"
    "Reply with JSON: name, description, input_schema, example_input, code."
)

SPEC_CASES = [
    "find when a function was last changed and by whom, given a file path and line range",
    "list all functions that have no callers",
]


def chat(model, messages, max_tokens, **extra):
    # max_tokens stops runaway generations (qwen3:4b once ran 27 minutes on one question)
    if model.startswith("qwen3"):
        # `think: false` alone did not stop qwen3 reasoning in its reply; /no_think is its own switch
        messages = [*messages[:-1], {**messages[-1], "content": messages[-1]["content"] + " /no_think"}]
    body = {"model": model, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "num_predict": max_tokens}, **extra}
    try:
        return post("/api/chat", body)
    except urllib.error.HTTPError as err:
        if "does not support thinking" not in err.read().decode(errors="replace"):
            raise
        body.pop("think")
        return post("/api/chat", body)


def post(path, body):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return json.load(res)


def speed(res):
    tokens, ns = res.get("eval_count", 0), res.get("eval_duration", 0)
    return round(tokens / (ns / 1e9), 1) if ns else 0.0


def timed_chat(*args, **kwargs):
    """Return (response or None, seconds, error)."""
    start = time.perf_counter()
    try:
        res, error = chat(*args, **kwargs), None
    except (TimeoutError, urllib.error.URLError) as err:
        res, error = None, f"{type(err).__name__}: {err}"
    return res, round(time.perf_counter() - start, 1), error


def run_tool_case(model, question, expected, check):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    res, seconds, error = timed_chat(model, messages, 256, tools=TOOLS)
    if res is None:
        return {"question": question, "expected": expected, "got": None, "args": {}, "n_calls": 0,
                "ok": False, "seconds": seconds, "tok_per_s": 0.0, "tokens": 0, "error": error, "text": ""}
    calls = res["message"].get("tool_calls") or []
    name = calls[0]["function"]["name"] if calls else None
    args = calls[0]["function"].get("arguments", {}) if calls else {}
    ok = len(calls) == 1 and name == expected and check(args)
    return {"question": question, "expected": expected, "got": name, "args": args, "n_calls": len(calls),
            "ok": ok, "seconds": seconds, "tok_per_s": speed(res), "tokens": res.get("eval_count", 0),
            "done_reason": res.get("done_reason"), "text": "" if calls else res["message"].get("content", "")[:300]}


def run_spec_case(model, task):
    messages = [{"role": "user", "content": SPEC_PROMPT.replace("TASK", task)}]
    res, seconds, error = timed_chat(model, messages, 1024, format=TOOL_SPEC_SCHEMA)
    if res is None:
        return {"task": task, "ok": False, "seconds": seconds, "tok_per_s": 0.0, "error": error, "code": ""}
    content = res["message"].get("content", "")
    try:
        spec = json.loads(content)
        code = spec.get("code", "")
        if "def run(args, ctx)" not in code:  # the prompt asks for the body only; wrap it in the template
            code = "def run(args, ctx):\n" + "\n".join("    " + line for line in code.splitlines())
        ok = isinstance(spec.get("input_schema"), dict)
        compile(code, "<tool>", "exec")  # syntax check only, never executed
    except (json.JSONDecodeError, SyntaxError):
        spec, ok = None, False
    return {"task": task, "ok": ok, "seconds": seconds, "tok_per_s": speed(res), "code": (spec or {}).get("code", content)[:800]}


def test_model(model):
    print(f"\n== {model}", flush=True)
    start = time.perf_counter()
    post("/api/generate", {"model": model, "prompt": "", "keep_alive": "10m"})
    load = round(time.perf_counter() - start, 1)
    print(f"  loaded in {load}s", flush=True)
    tools, specs = [], []
    for case in TOOL_CASES:
        r = run_tool_case(model, *case)
        tools.append(r)
        extra = r.get("error") or f"{r['tokens']} tok, {r['tok_per_s']} tok/s, {r.get('done_reason')}"
        print(f"  [{'ok' if r['ok'] else 'FAIL'}] {r['seconds']:>6}s  {r['expected']:<22} got {r['got']} {r['args']}"
              f"  ({extra})", flush=True)
        if r["text"]:
            print(f"         text: {r['text'][:150]!r}", flush=True)
    for task in SPEC_CASES:
        r = run_spec_case(model, task)
        specs.append(r)
        print(f"  [{'ok' if r['ok'] else 'FAIL'}] {r['seconds']:>6}s  tool spec: {task}", flush=True)
    post("/api/generate", {"model": model, "prompt": "", "keep_alive": 0})  # unload to free RAM
    all_runs = tools + specs
    return {
        "model": model,
        "load_seconds": load,
        "tool_calls_ok": sum(r["ok"] for r in tools),
        "tool_calls_total": len(tools),
        "specs_ok": sum(r["ok"] for r in specs),
        "specs_total": len(specs),
        "avg_seconds": round(sum(r["seconds"] for r in all_runs) / len(all_runs), 1),
        "avg_tok_per_s": round(sum(r["tok_per_s"] for r in all_runs) / len(all_runs), 1),
        "tool_cases": tools,
        "spec_cases": specs,
    }


def main():
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for m in MODELS:
        results.append(test_model(m))
        RESULTS.write_text(json.dumps(results, indent=2))  # save after each model
    print("\n| Model | Load (s) | Tool calls | Tool specs | Avg response (s) | Avg tok/s |")
    print("| --- | --- | --- | --- | --- | --- |")
    for r in results:
        print(f"| {r['model']} | {r['load_seconds']} | {r['tool_calls_ok']}/{r['tool_calls_total']} | "
              f"{r['specs_ok']}/{r['specs_total']} | {r['avg_seconds']} | {r['avg_tok_per_s']} |")
    print(f"\nDetails: {RESULTS}")


if __name__ == "__main__":
    main()
