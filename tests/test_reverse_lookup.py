"""API tests for Reverse Lookup — gene signature -> cell type (P: v1.1)."""

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
        data.weights("Blood")
    except ArtifactsNotBuilt as exc:
        pytest.skip(str(exc))
    return TestClient(app)


def test_cd8_signature_finds_cd8_t_cell(client: TestClient) -> None:
    r = client.get("/reverse-lookup", params={"genes": "CD3D,CD3E,CD8A,CD8B,GZMK"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_confident"] is True
    assert body["hits"], "expected ranked hits"
    # The top hit should be a CD8 T cell.
    assert "CD8" in body["hits"][0]["ontology_label"]
    # Hits are sorted by descending score.
    scores = [h["score"] for h in body["hits"]]
    assert scores == sorted(scores, reverse=True)


def test_matched_and_unknown_partition_query(client: TestClient) -> None:
    body = client.get(
        "/reverse-lookup", params={"genes": "CD3D, NOTAREALGENE, CD8A"}
    ).json()
    assert "NOTAREALGENE" in body["unknown_genes"]
    assert set(body["matched_genes"]).isdisjoint(body["unknown_genes"])
    assert set(body["matched_genes"]) | set(body["unknown_genes"]) == set(
        body["query_genes"]
    )


def test_all_unknown_genes_not_confident(client: TestClient) -> None:
    body = client.get("/reverse-lookup", params={"genes": "FAKE1 FAKE2"}).json()
    assert body["is_confident"] is False
    assert body["hits"] == []
    assert body["matched_genes"] == []


def test_organ_filter_restricts_hits(client: TestClient) -> None:
    body = client.get(
        "/reverse-lookup", params={"genes": "CD3D,CD8A,GZMK", "organ": "Blood"}
    ).json()
    assert body["hits"]
    assert all(h["organ"] == "Blood" for h in body["hits"])


def test_empty_query_rejected(client: TestClient) -> None:
    assert client.get("/reverse-lookup", params={"genes": "  "}).status_code == 400


def test_limit_caps_results(client: TestClient) -> None:
    body = client.get(
        "/reverse-lookup", params={"genes": "CD3D,CD8A", "limit": 3}
    ).json()
    assert len(body["hits"]) <= 3
