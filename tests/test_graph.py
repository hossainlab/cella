"""API tests for the Relationship Graph Explorer (P4).

Exercise the emitted graph artifacts through the FastAPI app. Needs the `api`
group and built graph artifacts (`cella build` + `cella graph`); skipped
if either is missing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from cella.api import data  # noqa: E402
from cella.api.data import ArtifactsNotBuilt  # noqa: E402
from cella.api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    try:
        data.graph_nodes()
        data.graph_edges()
    except ArtifactsNotBuilt as exc:
        pytest.skip(str(exc))
    return TestClient(app)


def test_full_graph(client: TestClient) -> None:
    body = client.get("/graph").json()
    assert len(body["organs"]) == 12
    assert body["n_total_nodes"] == len(body["nodes"]) > 0
    assert body["edges"], "expected edges in the full graph"
    node = body["nodes"][0]
    assert {"cl_id", "label", "primary_organ", "total_cells", "x", "y"} <= node.keys()


def test_edges_reference_present_nodes(client: TestClient) -> None:
    body = client.get("/graph").json()
    ids = {n["cl_id"] for n in body["nodes"]}
    for e in body["edges"]:
        assert e["source"] in ids and e["target"] in ids
        assert 0.0 <= e["similarity"] <= 1.0


def test_similarity_floor_filters_edges(client: TestClient) -> None:
    loose = client.get("/graph", params={"min_similarity": 0.0}).json()
    tight = client.get("/graph", params={"min_similarity": 0.8}).json()
    assert len(tight["edges"]) <= len(loose["edges"])
    assert all(e["similarity"] >= 0.8 for e in tight["edges"])


def test_organ_filter(client: TestClient) -> None:
    body = client.get("/graph", params={"organ": "Lung"}).json()
    assert 0 < len(body["nodes"]) < body["n_total_nodes"]
    ids = {n["cl_id"] for n in body["nodes"]}
    for e in body["edges"]:  # edges stay within the filtered node set
        assert e["source"] in ids and e["target"] in ids


def test_organ_filter_unknown(client: TestClient) -> None:
    assert client.get("/graph", params={"organ": "Nonexistent"}).status_code == 404


def test_edge_detail(client: TestClient) -> None:
    edges = client.get("/graph").json()["edges"]
    top = max(edges, key=lambda e: e["similarity"])
    r = client.get(f"/graph/edge/{top['source']}/{top['target']}")
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["cl_id"] == top["source"]
    assert body["target"]["cl_id"] == top["target"]
    assert body["similarity"] == pytest.approx(top["similarity"], rel=1e-4)
    # Shared genes are defining (positive) in both types.
    for g in body["shared_genes"]:
        assert g["source_coef"] > 0 and g["target_coef"] > 0


def test_edge_detail_order_independent(client: TestClient) -> None:
    top = max(client.get("/graph").json()["edges"], key=lambda e: e["similarity"])
    ab = client.get(f"/graph/edge/{top['source']}/{top['target']}").json()
    ba = client.get(f"/graph/edge/{top['target']}/{top['source']}").json()
    assert ab["similarity"] == ba["similarity"]
    assert {g["gene"] for g in ab["shared_genes"]} == {
        g["gene"] for g in ba["shared_genes"]
    }


def test_edge_detail_unknown_node(client: TestClient) -> None:
    assert client.get("/graph/edge/CL:9999999/CL:0000235").status_code == 404
