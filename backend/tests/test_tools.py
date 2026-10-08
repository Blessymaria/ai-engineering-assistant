from pathlib import Path

import pytest

from app.graph.build import DEFAULT_WORKSPACE
from app.tools.registry import CORE_TOOLS, run_tool
from app.tools.repo import LoadedRepo, ToolError
from app.tools.search import tokens

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


def ids(result):
    return [r.get("id") for r in result["results"]]


# --- registry -------------------------------------------------------------

def test_exactly_four_core_tools():
    assert sorted(CORE_TOOLS) == ["list_files", "query_graph", "read_file", "search_code"]


@pytest.mark.parametrize("name, args, message", [
    ("nope", {}, "unknown tool"),
    ("read_file", {}, "missing required"),
    ("read_file", {"path": "x.py", "colour": 1}, "unknown argument"),
    ("read_file", {"path": 3}, "must be a string"),
    ("query_graph", {"node": "x", "relation": "friends"}, "must be one of"),
    ("search_code", "query", "JSON object"),
])
def test_run_tool_rejects_bad_input(repo, name, args, message):
    with pytest.raises(ToolError, match=message):
        run_tool(repo, name, args)


def test_run_tool_accepts_numeric_strings(repo):
    result = run_tool(repo, "read_file", {"path": "shop/db/repo.py", "start": "2", "end": "3"})
    assert (result["start"], result["end"]) == (2, 3)


# --- search_code ----------------------------------------------------------

def test_tokens_split_names():
    assert tokens("ArticlesRepository.create_article") == {"article", "repository", "create"}
    assert tokens("HTTPException") == {"http", "exception"}


def test_search_exact_symbol_first(repo):
    result = run_tool(repo, "search_code", {"query": "create_order"})
    assert result["results"][0]["id"] == "shop.services.orders.create_order"
    assert result["results"][0]["doc"] == "Validate and save an order."


def test_search_route(repo):
    result = run_tool(repo, "search_code", {"query": "POST /shop/v1/orders"})
    top = result["results"][0]
    assert (top["kind"], top["name"]) == ("route", "POST /shop/v1/orders")


def test_search_words_match_split_names(repo):
    result = run_tool(repo, "search_code", {"query": "order repo"})
    assert result["results"][0]["id"] == "shop.db.repo.OrderRepo"


def test_search_source_lines_name_enclosing_symbol(repo):
    result = run_tool(repo, "search_code", {"query": "empty order"})
    line = next(r for r in result["results"] if r["kind"] == "line")
    assert line["path"] == "shop/services/orders.py"
    assert line["in"] == "shop.services.orders.validate"


def test_search_finds_docs(repo):
    result = run_tool(repo, "search_code", {"query": "User guide"})
    assert result["results"][0]["kind"] == "doc"


def test_search_limit_and_empty_query(repo):
    assert len(run_tool(repo, "search_code", {"query": "order", "limit": 2})["results"]) == 2
    with pytest.raises(ToolError):
        run_tool(repo, "search_code", {"query": "  "})


# --- query_graph ----------------------------------------------------------

def test_callees_with_status(repo):
    result = run_tool(repo, "query_graph", {"node": "shop.services.orders.create_order", "relation": "callees"})
    status = {r["id"]: r["status"] for r in result["results"]}
    assert status["shop.services.orders.validate"] == "resolved"
    assert status["shop.db.repo.OrderRepo.save"] == "ambiguous"
    assert status["unresolved:notifier"] == "unresolved"
    assert "note_calls" in result


def test_callees_depth_follows_only_resolved(repo):
    result = run_tool(repo, "query_graph", {"node": "shop.api.routes.post_order", "relation": "callees", "depth": 3})
    by_id = {r["id"]: r for r in result["results"]}
    assert by_id["shop.services.orders.validate"]["depth"] == 2
    assert by_id["shop.services.orders.validate"]["via"] == "shop.services.orders.create_order"
    # OrderRepo.save is reached only through an ambiguous call, so its own callees are not expanded
    assert "shop.db.repo.BaseRepo.get" not in by_id


def test_callers_by_short_name(repo):
    result = run_tool(repo, "query_graph", {"node": "create_order", "relation": "callers"})
    assert set(ids(result)) == {"shop.api.routes.post_order", "shop.api.routes.via_package"}


def test_ambiguous_short_name_lists_candidates(repo):
    with pytest.raises(ToolError, match="matches 2 nodes"):
        run_tool(repo, "query_graph", {"node": "save", "relation": "callers"})


def test_unknown_node(repo):
    with pytest.raises(ToolError, match="search_code"):
        run_tool(repo, "query_graph", {"node": "does_not_exist", "relation": "callers"})


def test_handlers_both_directions(repo):
    route = run_tool(repo, "query_graph", {"node": "POST /shop/v1/orders", "relation": "handlers"})
    assert ids(route) == ["shop.api.routes.post_order"]
    handler = run_tool(repo, "query_graph", {"node": "shop.api.routes.post_order", "relation": "handlers"})
    assert handler["results"][0]["name"] == "POST /shop/v1/orders"


@pytest.mark.parametrize("node, relation, expected", [
    ("shop.api.routes", "imports", "shop.db.repo"),
    ("shop.db.repo", "imported_by", "shop.api.routes"),
    ("shop.db.repo", "contains", "shop.db.repo.OrderRepo"),
    ("shop.db.repo.OrderRepo", "inherits", "shop.db.repo.BaseRepo"),
    ("shop.db.repo.BaseRepo", "subclasses", "shop.db.repo.UserRepo"),
    ("shop.services.orders.validate", "mentions", "doc:docs/guide.rst#L5"),
])
def test_other_relations(repo, node, relation, expected):
    assert expected in ids(run_tool(repo, "query_graph", {"node": node, "relation": relation}))


# --- read_file ------------------------------------------------------------

def test_read_file_numbered_lines(repo):
    result = run_tool(repo, "read_file", {"path": "shop/db/repo.py", "start": 1, "end": 2})
    assert result["content"] == "   1| class BaseRepo:\n   2|     def get(self, key):"
    assert result["total_lines"] == 18
    assert "note" in result


def test_read_file_accepts_windows_and_dot_paths(repo):
    assert run_tool(repo, "read_file", {"path": ".\\shop\\db\\repo.py"})["path"] == "shop/db/repo.py"


@pytest.mark.parametrize("args, message", [
    ({"path": "../../../app/main.py"}, "outside"),
    ({"path": "shop/db/repo.py", "start": 500}, "past the end"),
    ({"path": "shop/db/repo.py", "start": 5, "end": 2}, "before start"),
    ({"path": "shop/nothing.py"}, "not a file"),
])
def test_read_file_errors(repo, args, message):
    with pytest.raises(ToolError, match=message):
        run_tool(repo, "read_file", args)


def test_read_file_caps_lines(repo, monkeypatch):
    from app.tools import files
    monkeypatch.setattr(files, "MAX_LINES", 3)
    result = run_tool(repo, "read_file", {"path": "shop/services/orders.py"})
    assert (result["start"], result["end"]) == (1, 3)


# --- list_files -----------------------------------------------------------

def test_list_files_depth(repo):
    result = run_tool(repo, "list_files", {"depth": 1})
    paths = {e["path"]: e for e in result["entries"]}
    assert "README.md" in paths
    assert paths["shop/"]["files"] == 9
    assert "shop/api/routes.py" not in paths


def test_list_files_subfolder(repo):
    result = run_tool(repo, "list_files", {"path": "shop/db"})
    assert [e["path"] for e in result["entries"]] == ["shop/db/__init__.py", "shop/db/repo.py"]


def test_list_files_errors(repo):
    with pytest.raises(ToolError, match="outside"):
        run_tool(repo, "list_files", {"path": ".."})
    with pytest.raises(ToolError, match="not a directory"):
        run_tool(repo, "list_files", {"path": "README.md"})


# --- demo repository (skipped unless it has been cloned) -------------------

DEMO = DEFAULT_WORKSPACE / "fastapi-realworld-example-app"


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    if not DEMO.is_dir():
        pytest.skip("demo repository not cloned; run python -m app.graph.build <url>")
    return LoadedRepo.build(str(DEMO), tmp_path_factory.mktemp("ws"))


def test_demo_route_search(demo):
    top = run_tool(demo, "search_code", {"query": "POST /articles"})["results"][0]
    assert top["name"] == "POST /articles"
    handler = run_tool(demo, "query_graph", {"node": top["id"], "relation": "handlers"})["results"][0]
    assert handler["id"] == "app.api.routes.articles.articles_resource.create_new_article"


def test_demo_flow_follows_the_injected_repository(demo):
    """Multi-hop: route handler -> repository (injected as `articles_repo: ArticlesRepository = Depends(...)`)
    -> its helpers. Before annotation-based resolution the walk stopped at the handler."""
    result = run_tool(demo, "query_graph", {"node": "create_new_article", "relation": "callees", "depth": 3})
    status = {r["id"]: (r["status"], r["depth"]) for r in result["results"]}
    repo = "app.db.repositories.articles.ArticlesRepository"
    assert status[f"{repo}.create_article"] == ("resolved", 1)
    assert status["app.services.articles.check_article_exists"] == ("resolved", 1)
    assert status[f"{repo}._link_article_with_tags"] == ("resolved", 2)  # inside the repository
    assert status[f"{repo}.get_tags_for_article_by_slug"] == ("resolved", 3)
    # self._tags_repo = TagsRepository(conn) in __init__
    assert status["app.db.repositories.tags.TagsRepository.create_tags_that_dont_exist"][0] == "resolved"
    # SQL queries loaded by aiosql at runtime are still honestly unresolved
    assert status["unresolved:queries.create_new_article"][0] == "unresolved"


def test_demo_read_and_list(demo):
    assert run_tool(demo, "read_file", {"path": "app/main.py", "start": 1, "end": 1})["content"].startswith("   1| ")
    entries = {e["path"] for e in run_tool(demo, "list_files", {})["entries"]}
    assert {"app/", "app/api/", "README.rst"} <= entries
