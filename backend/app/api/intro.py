"""A 2-3 sentence introduction to the loaded repository, shown before the first question.

One short model call (no tools, no agent loop) over a few facts from the graph and the start of the README.
The result is cached per repository and commit. If the model cannot be reached, a plain sentence built
from the same facts is returned instead (and not cached, so the model is tried again next time).
"""

import json
import sys
import threading
from collections import Counter
from pathlib import Path

from app.api.suggest import _code, _is_test
from app.llm.base import LLMError, LLMProvider
from app.tools.repo import LoadedRepo, ToolError

README_CHARS = 1500
MAX_TOKENS = 200
TOP_LIBRARIES = 6
TOP_PACKAGES = 8
ROUTE_EXAMPLES = 10
TEST_LIBRARIES = {"pytest", "mock", "hypothesis", "nose", "tox", "faker", "factory", "freezegun", "responses"}
# README lines that carry no meaning for an introduction: images, badges, links-only lines, rules, HTML
NOISE = (".. ", ":target:", ":alt:", "|", "[![", "![", "<", "---", "===", "***")

PROMPT = """Write a 2-3 sentence introduction to this Python repository for a developer who has never seen it.
Say what the application does (its routes and packages show its domain) and what it is built with.
Use only the facts below; do not guess features, and do not list file or function counts.
Plain prose, no headings, no lists, no Markdown, under 70 words.

{facts}"""

_lock = threading.Lock()  # one model call at a time; a second request waits and then reads the cache


def _readme(repo: LoadedRepo) -> str:
    names = sorted((f for f in repo.files if "/" not in f and Path(f).stem.lower() == "readme"), key=len)
    for name in names:
        try:
            text = repo.text(name)
        except ToolError:
            continue
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line and not line.startswith(NOISE))[:README_CHARS]
    return ""


def _packages(graph) -> list[str]:
    """The main packages; when everything sits in one top-level package (app/), its subpackages."""
    modules = [n for n, _ in _code(graph, "module") if "." in n]
    tops = Counter(n.split(".")[0] for n in modules)
    if len(tops) == 1:
        tops = Counter(".".join(n.split(".")[:2]) for n in modules if n.count(".") >= 2)
    return [name for name, _ in tops.most_common(TOP_PACKAGES)]


def repo_facts(repo: LoadedRepo) -> dict:
    graph = repo.graph
    libraries = Counter()
    for u, v, d in graph.edges(data=True):
        if d["kind"] == "IMPORTS" and graph.nodes[v]["kind"] == "external" and not _is_test(u, graph.nodes[u]):
            top = graph.nodes[v]["name"].split(".")[0]
            if top and top not in sys.stdlib_module_names and top not in TEST_LIBRARIES:
                libraries[top] += 1
    routes = sorted(d["name"] for _, d in _code(graph, "route"))
    by_path: dict[str, list[str]] = {}  # "GET /articles", "POST /articles" -> "GET|POST /articles"
    for name in routes:
        method, _, path = name.partition(" ")
        by_path.setdefault(path, []).append(method)
    return {
        "name": repo.root.name,
        "python_files": sum(1 for f in repo.files if f.endswith(".py")),
        "routes": len(routes),
        "route_examples": [f"{'|'.join(dict.fromkeys(m))} {p}" for p, m in sorted(by_path.items(), key=lambda kv: len(kv[0]))]
                          [:ROUTE_EXAMPLES],
        "classes": len(_code(graph, "class")),
        "functions": len(_code(graph, "function")),
        "main_libraries": [name for name, _ in libraries.most_common(TOP_LIBRARIES)],
        "main_packages": _packages(graph),
        "readme_start": _readme(repo),
    }


def facts_intro(facts: dict) -> str:
    """The fallback: one plain sentence, with nothing the graph does not show."""
    built = f", built with {', '.join(facts['main_libraries'][:3])}" if facts["main_libraries"] else ""
    routes = f" and {facts['routes']} web routes" if facts["routes"] else ""
    return (f"{facts['name']} is a Python project{built}. It has {facts['python_files']} Python files, "
            f"{facts['functions']} functions{routes}.")


def _cache_file(workspace: Path, repo: LoadedRepo) -> Path:
    commit = (repo.graph.graph.get("commit") or "local")[:12]
    return workspace / "intros" / f"{repo.root.name}-{commit}.json"


def repo_intro(repo: LoadedRepo, llm: LLMProvider, workspace: Path) -> dict:
    cache = _cache_file(workspace, repo)
    with _lock:
        if cache.is_file():
            return {**json.loads(cache.read_text(encoding="utf-8")), "cached": True}
        facts = repo_facts(repo)
        try:
            reply = llm.chat([{"role": "user", "content": PROMPT.format(facts=json.dumps(facts, indent=1))}],
                             max_tokens=MAX_TOKENS)
            text = " ".join(reply.content.split())
        except LLMError:
            text = ""
        if not text:
            return {"text": facts_intro(facts), "source": "facts", "cached": False}
        result = {"text": text, "source": "model"}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result), encoding="utf-8")
        return {**result, "cached": False}
