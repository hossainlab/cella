"""API tests for the Cross-Organ Fingerprint Explorer (P3).

Exercise the real emitted artifacts through the FastAPI app. Needs the `api`
dependency group and built processed artifacts; skipped if either is missing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from cella.api import data  # noqa: E402
from cella.api.data import ArtifactsNotBuilt  # noqa: E402
from cella.api.main import app  # noqa: E402

MACROPHAGE = "CL:0000235"  # present in many organs — a good multi-organ fixture


@pytest.fixture(scope="module")
def client() -> TestClient:
    try:
        data.markers()  # fail fast (skip) if artifacts are not built
    except ArtifactsNotBuilt as exc:
        pytest.skip(str(exc))
    return TestClient(app)


def test_fingerprint_shape(client: TestClient) -> None:
    r = client.get(f"/fingerprints/{MACROPHAGE}", params={"top_n": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["cl_id"] == MACROPHAGE
    assert body["ontology_label"] == "macrophage"
    assert len(body["organs"]) >= 2  # multi-organ, so a fingerprint is comparable
    assert len(body["per_organ"]) == len(body["organs"])
    assert body["genes"], "expected a non-empty pivoted gene list"


def test_fingerprint_genes_sorted_and_signed(client: TestClient) -> None:
    body = client.get(f"/fingerprints/{MACROPHAGE}", params={"top_n": 5}).json()
    genes = body["genes"]
    # Sorted most-shared first.
    counts = [g["n_organs"] for g in genes]
    assert counts == sorted(counts, reverse=True)
    # Every cell carries a signed coef consistent with its direction.
    for g in genes:
        assert g["n_organs"] == len(g["cells"])
        for c in g["cells"]:
            if c["direction"] == "positive":
                assert c["coef"] > 0
            else:
                assert c["coef"] < 0


def test_fingerprint_unknown_cl_id(client: TestClient) -> None:
    assert client.get("/fingerprints/CL:9999999").status_code == 404


def test_gene_across_organs(client: TestClient) -> None:
    genes = client.get(
        f"/fingerprints/{MACROPHAGE}", params={"top_n": 5}
    ).json()["genes"]
    gene = genes[0]["gene"]
    r = client.get(f"/fingerprints/{MACROPHAGE}/gene/{gene}")
    assert r.status_code == 200
    body = r.json()
    assert body["gene"] == gene
    assert body["present_in"], "top gene should be present in >=1 organ"
    # present_in ordered by descending |coef|.
    mags = [abs(w["coef"]) for w in body["present_in"]]
    assert mags == sorted(mags, reverse=True)
    # present and absent partition the organs the type appears in.
    present = {w["organ"] for w in body["present_in"]}
    assert present.isdisjoint(body["absent_in"])


def test_gene_case_insensitive(client: TestClient) -> None:
    gene = client.get(
        f"/fingerprints/{MACROPHAGE}", params={"top_n": 5}
    ).json()["genes"][0]["gene"]
    lower = client.get(f"/fingerprints/{MACROPHAGE}/gene/{gene.lower()}").json()
    upper = client.get(f"/fingerprints/{MACROPHAGE}/gene/{gene.upper()}").json()
    assert lower["present_in"] == upper["present_in"]
