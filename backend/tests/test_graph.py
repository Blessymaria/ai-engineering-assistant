from pathlib import Path

import pytest

from app.graph.build import build_graph
from app.graph.store import load_graph, save_graph
from app.ingest.docs import split_sections
from app.ingest.loader import load_repo
from app.ingest.parser import module_name, parse_module

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    return build_graph(load_repo(str(FIXTURE), tmp_path_factory.mktemp("ws")))


def edges(graph, kind):
    return {(u, v, d.get("status")) for u, v, d in graph.edges(data=True) if d["kind"] == kind}


def test_module_names():
    assert module_name("shop/api/routes.py") == "shop.api.routes"
    assert module_name("shop/__init__.py") == "shop"
    assert module_name("src/pkg/mod.py") == "pkg.mod"


def test_nodes_have_location_and_docstring(graph):
    node = graph.nodes["shop.services.orders.create_order"]
    assert node["kind"] == "function"
    assert node["path"] == "shop/services/orders.py"
    assert (node["start"], node["end"]) == (12, 18)
    assert node["docstring"] == "Validate and save an order."
    assert graph.nodes["shop.db.repo.OrderRepo"]["kind"] == "class"
    assert graph.nodes["shop.services.orders"]["docstring"] == "Order service."


def test_contains(graph):
    contains = edges(graph, "CONTAINS")
    assert ("shop.db.repo", "shop.db.repo.OrderRepo", None) in contains
    assert ("shop.db.repo.OrderRepo", "shop.db.repo.OrderRepo.save", None) in contains


def test_imports_including_relative_and_external(graph):
    imports = {(u, v) for u, v, _ in edges(graph, "IMPORTS")}
    assert ("shop.api.routes", "shop.db.repo") in imports  # from ..db.repo import ...
    assert ("shop.api.routes", "shop.services") in imports
    assert ("shop.api.routes", "ext:fastapi") in imports
    assert graph.nodes["ext:fastapi"]["kind"] == "external"


def test_inherits(graph):
    inherits = {(u, v) for u, v, _ in edges(graph, "INHERITS")}
    assert ("shop.db.repo.OrderRepo", "shop.db.repo.BaseRepo") in inherits
    assert ("shop.db.repo.UserRepo", "shop.db.repo.BaseRepo") in inherits


def test_routes_include_router_prefixes(graph):
    # include_router(prefix="/shop") + APIRouter(prefix="/v1") + route path
    handles = {(graph.nodes[u]["name"], v) for u, v, _ in edges(graph, "HANDLES")}
    assert handles == {
        ("POST /shop/v1/orders", "shop.api.routes.post_order"),
        ("GET /shop/v1/orders/{order_id}", "shop.api.routes.get_order"),
    }


@pytest.mark.parametrize("caller, callee", [
    ("shop.api.routes.post_order", "shop.services.orders.create_order"),  # from-import
    ("shop.api.routes.get_order", "shop.services.orders.load_order"),  # module alias
    ("shop.api.routes.via_package", "shop.services.orders.create_order"),  # re-export in __init__
    ("shop.services.orders.create_order", "shop.services.orders.validate"),  # same module
    ("shop.services.orders.create_order", "shop.db.repo.OrderRepo"),  # class instantiation
    ("shop.db.repo.OrderRepo.save", "shop.db.repo.BaseRepo.get"),  # self. via base class
    ("shop.db.repo.BaseRepo.get", "shop.db.repo.BaseRepo._fetch"),  # self. in same class
    ("shop.services.orders.create_order", "ext:json.dumps"),  # library call
    ("shop.api.routes", "ext:fastapi.APIRouter"),  # module-level call
])
def test_resolved_calls(graph, caller, callee):
    assert (caller, callee, "resolved") in edges(graph, "CALLS")


def test_ambiguous_calls_list_all_candidates(graph):
    calls = edges(graph, "CALLS")
    assert ("shop.services.orders.create_order", "shop.db.repo.OrderRepo.save", "ambiguous") in calls
    assert ("shop.services.orders.create_order", "shop.db.repo.UserRepo.save", "ambiguous") in calls
    # A name-only match is not confirmed, even with a single candidate.
    assert ("shop.services.orders.load_order", "shop.db.repo.BaseRepo.get", "ambiguous") in calls


def test_unresolved_calls(graph):
    calls = edges(graph, "CALLS")
    assert ("shop.services.orders.create_order", "unresolved:notifier", "unresolved") in calls
    assert graph.nodes["unresolved:notifier"]["kind"] == "unresolved"


def test_builtins_and_local_method_calls_are_skipped(graph):
    targets = {v for _, v, _ in edges(graph, "CALLS")}
    assert not any("ValueError" in t for t in targets)


def test_syntax_error_keeps_module_node(graph):
    assert "error" in graph.nodes["shop.broken"]


def test_doc_sections_and_mentions(graph):
    docs = {d["name"] for _, d in graph.nodes(data=True) if d["kind"] == "doc"}
    assert docs == {"README.md", "Shop", "Saving", "guide.rst", "User guide", "Storage"}
    mentions = {(graph.nodes[u]["name"], v) for u, v, _ in edges(graph, "MENTIONS")}
    assert mentions == {
        ("Shop", "shop.services.orders.create_order"),
        ("Shop", "shop.db.repo.OrderRepo"),
        ("User guide", "shop.services.orders.validate"),
        ("Storage", "shop.db.repo.BaseRepo"),
    }  # `save` matches two symbols, so no edge


def test_rst_transition_line_is_not_a_heading():
    sections = split_sections("x.rst", "Intro\n\n----------\n\nTitle\n=====\ntext\n")
    assert [s.title for s in sections] == ["x.rst", "Title"]


def test_headings_inside_code_fences_are_ignored():
    sections = split_sections("x.md", "# A\n```\n# not a heading\n```\n# B\ntext\n")
    assert [s.title for s in sections] == ["A", "B"]


def test_parse_module_detects_flask_routes():
    source = '@app.route("/items", methods=["GET", "POST"])\ndef items():\n    pass\n'
    _, _, routes = parse_module("web.py", source)
    assert [(r.method, r.path, r.handler) for r in routes] == [("GET|POST", "/items", "web.items")]


def test_save_and_load_roundtrip(graph, tmp_path):
    path = tmp_path / "g.json"
    save_graph(graph, path)
    loaded = load_graph(path)
    assert loaded.number_of_nodes() == graph.number_of_nodes()
    assert loaded.number_of_edges() == graph.number_of_edges()
    assert loaded.graph["root"] == graph.graph["root"]
