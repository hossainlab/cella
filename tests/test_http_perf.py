"""Transport-level performance behavior: gzip + cache headers on the data API."""

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
    except ArtifactsNotBuilt as exc:
        pytest.skip(str(exc))
    return TestClient(app)


def test_large_response_is_gzipped(client: TestClient) -> None:
    r = client.get("/graph", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_data_responses_are_cacheable(client: TestClient) -> None:
    r = client.get("/graph")
    assert "max-age" in r.headers.get("cache-control", "")
    assert r.headers.get("etag")


def test_health_is_not_cached(client: TestClient) -> None:
    r = client.get("/health")
    assert "cache-control" not in r.headers
    assert "etag" not in r.headers


def test_matching_etag_returns_304(client: TestClient) -> None:
    etag = client.get("/graph").headers["etag"]
    r = client.get("/graph", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""


def test_stale_etag_returns_full_body(client: TestClient) -> None:
    r = client.get("/graph", headers={"If-None-Match": '"different-release"'})
    assert r.status_code == 200
    assert r.json()["nodes"]
