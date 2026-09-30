from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.diagram import build_mermaid
from app.agent.evidence import EvidenceStore
from app.api import routes
from app.main import app
from app.tools.registry import run_tool
from app.tools.repo import LoadedRepo

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return LoadedRepo.build(str(FIXTURE), tmp_path_factory.mktemp("ws"))


def store_with(repo, *queries):
    store = EvidenceStore()
    for args in queries:
        store.add("query_graph", args, run_tool(repo, "query_graph", args))
    return store


# --- diagram ------------------------------------------------------------------

def test_flow_diagram_solid_and_dashed(repo):
    diagram = build_mermaid(store_with(
        repo,
        {"node": "POST /shop/v1/orders", "relation": "handlers"},
        {"node": "shop.api.routes.post_order", "relation": "callees", "depth": 2},
    ))
    lines = diagram.splitlines()
    assert lines[0] == "flowchart TD"
    label = {l.split('["')[1].rstrip('"]'): l.split("[")[0].strip() for l in lines if '["' in l}
    assert {"POST /shop/v1/orders", "post_order", "create_order", "validate", "OrderRepo.save",
            "notifier ?"} <= set(label)
    assert f"{label['POST /shop/v1/orders']} --> {label['post_order']}" in diagram
    assert f"{label['post_order']} --> {label['create_order']}" in diagram
    assert f"{label['create_order']} --> {label['validate']}" in diagram
    assert f"{label['create_order']} -.->|ambiguous| {label['OrderRepo.save']}" in diagram
    assert f"{label['create_order']} -.->|unresolved| {label['notifier ?']}" in diagram
    assert "json.dumps" not in diagram  # library calls are left out


def test_callers_and_route_direction(repo):
    diagram = build_mermaid(store_with(
        repo,
        {"node": "shop.api.routes.post_order", "relation": "handlers"},
        {"node": "create_order", "relation": "callers"},
    ))
    label = {l.split('["')[1].rstrip('"]'): l.split("[")[0].strip() for l in diagram.splitlines() if '["' in l}
    assert f"{label['POST /shop/v1/orders']} --> {label['post_order']}" in diagram
    assert f"{label['via_package']} --> {label['create_order']}" in diagram


def test_no_graph_evidence_means_no_diagram(repo):
    store = EvidenceStore()
    store.add("list_files", {}, run_tool(repo, "list_files", {}))
    assert build_mermaid(store) is None


# --- repository endpoints -------------------------------------------------------

def test_get_repo_summary(repo, monkeypatch):
    monkeypatch.setattr(routes, "_state", {"repo": repo})
    data = TestClient(app).get("/api/repo").json()
    assert data["name"] == "shop" and data["kinds"]["route"] == 2 and data["nodes"] > 20


def test_load_repo_builds_saves_and_switches(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    monkeypatch.setenv("AIEA_ALLOWED_ROOTS", str(FIXTURE.parent))
    monkeypatch.setattr(routes, "_state", {"repo": None})
    response = TestClient(app).post("/api/repo", json={"source": str(FIXTURE)})
    assert response.status_code == 200
    assert response.json()["kinds"]["function"] > 5
    assert list((tmp_path / "graphs").glob("*.json"))
    assert routes._state["repo"].root == FIXTURE.resolve()


def test_load_repo_refuses_local_folders_outside_allowed_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path / "ws")
    monkeypatch.setenv("AIEA_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    response = TestClient(app).post("/api/repo", json={"source": str(FIXTURE)})
    assert response.status_code == 403 and "must be inside" in response.json()["detail"]


def test_allowed_roots_default_to_workspace_and_desktop(monkeypatch):
    monkeypatch.delenv("AIEA_ALLOWED_ROOTS", raising=False)
    roots = routes.allowed_roots()
    assert routes.DEFAULT_WORKSPACE.resolve() in roots and (Path.home() / "Desktop").resolve() in roots


@pytest.mark.parametrize("source, status", [(" ", 422), ("ftp://nope", 400)])
def test_load_repo_errors(tmp_path, monkeypatch, source, status):
    monkeypatch.setattr(routes, "DEFAULT_WORKSPACE", tmp_path)
    assert TestClient(app).post("/api/repo", json={"source": source}).status_code == status
