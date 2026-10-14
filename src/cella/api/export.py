"""Static export: write every fixed API response to files for a serverless site.

The public site can run with no backend (GitHub Pages). Responses that depend
only on a finite set of inputs - each organ, each cell type, each graph edge,
each GSEA collection - are produced here by calling the real FastAPI app
in-process and saving what it returns, so static and server mode serve the
same bytes by construction. Endpoints that take free text (reverse lookup,
gene and signature lookups) are computed in the browser from the compact
expression tables written by :func:`export_expression`.

Layout under ``out`` (mirrored by ``web/lib/static.ts``)::

    cell-types.json                     full registry (filtered client-side)
    cell-type-organ.json                (organ, curated label) -> CL id, label
    cl-relatives.json                   close ontology relatives per CL id
    markers/<CL>.json                   /markers/{cl}?top_n=10
    fingerprints/<CL>.json              /fingerprints/{cl}?top_n=10
    marker-rows/<CL>.json               raw marker rows (gene-across-organs)
    graph/all.json, graph/<Organ>.json  /graph?min_similarity=0[&organ=]
    graph/edge/<CLa>__<CLb>.json        /graph/edge/{a}/{b}, ids sorted
    organs.json
    organs/<slug>/{detail,embedding,markers,composition,tf,cci}.json
    organs/<slug>/gsea-<collection>.json
    organs/<slug>/fig-{umap,tf,cci}.json, fig-gsea-<collection>.json
    expr/<slug>.json, expr/<slug>.pct.bin.gz, expr/<slug>.mean.bin.gz

CL ids are written with ``:`` replaced by ``_`` so file names are portable.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

from cella.api import data
from cella.core.config import ORGANS

GSEA_COLLECTIONS = ("hallmark", "kegg", "go_bp", "immunologic", "oncogenic", "tft")
# Query parameters the frontend sends (web/app/**/page.tsx); a static file only
# answers the exact request it was generated from.
MARKER_TOP_N = 10
ORGAN_MARKERS_TOP_N = 5
TF_TOP_N = 5
GSEA_TOP_N = 5
CCI_LIMIT = 150
COMPOSITION_GROUP = "Dataset"


def cl_file(cl_id: str) -> str:
    return cl_id.replace(":", "_")


def slug(organ: str) -> str:
    return organ.replace(" ", "_")


class _Writer:
    def __init__(self, out: Path) -> None:
        import logging

        from fastapi.testclient import TestClient

        logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request otherwise

        from cella.api.main import app

        self.out = out
        self.client = TestClient(app)
        self.n_files = 0
        self.n_bytes = 0
        self.skipped: list[str] = []

    def save(self, rel: str, payload: object) -> None:
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        path.write_text(body)
        self.n_files += 1
        self.n_bytes += len(body)

    def get(self, url: str, rel: str, *, optional: bool = False) -> object | None:
        """GET ``url`` from the app and save the JSON body at ``rel``."""
        r = self.client.get(url)
        if r.status_code != 200:
            if optional:
                self.skipped.append(f"{url} -> {r.status_code}")
                return None
            raise RuntimeError(f"{url} -> {r.status_code}: {r.text[:200]}")
        payload = r.json()
        self.save(rel, payload)
        return payload


def export_api(out: Path) -> _Writer:
    """Write every fixed-input endpoint's response under ``out``."""
    w = _Writer(out)

    w.get("/cell-types?min_organs=1&limit=500", "cell-types.json")
    w.save("cell-type-organ.json", data.cell_type_organ().to_dict("records"))
    w.save(
        "cl-relatives.json",
        {k: sorted(v) for k, v in data.cl_relatives().items()},
    )

    markers = data.markers()
    for cl_id in sorted(data.registry()["cl_id"]):
        q = quote(cl_id)
        w.get(f"/markers/{q}?top_n={MARKER_TOP_N}", f"markers/{cl_file(cl_id)}.json", optional=True)
        # Single-organ types have no fingerprint (404 server-side too).
        w.get(
            f"/fingerprints/{q}?top_n={MARKER_TOP_N}",
            f"fingerprints/{cl_file(cl_id)}.json",
            optional=True,
        )
        rows = markers[markers["cl_id"] == cl_id]
        w.save(
            f"marker-rows/{cl_file(cl_id)}.json",
            rows[["organ", "gene", "coef", "rank", "direction"]].to_dict("records"),
        )

    w.get("/graph?min_similarity=0", "graph/all.json")
    for organ in ORGANS:
        w.get(
            f"/graph?min_similarity=0&organ={quote(organ)}",
            f"graph/{slug(organ)}.json",
            optional=True,
        )
    edges = data.graph_edges()
    for e in edges.itertuples():
        a, b = sorted((e.source, e.target))
        w.get(
            f"/graph/edge/{quote(a)}/{quote(b)}",
            f"graph/edge/{cl_file(a)}__{cl_file(b)}.json",
        )

    w.get("/organs", "organs.json")
    for organ in ORGANS:
        s = slug(organ)
        base = f"/organs/{s}"
        w.get(base, f"organs/{s}/detail.json")
        w.get(f"{base}/embedding", f"organs/{s}/embedding.json", optional=True)
        w.get(
            f"{base}/markers?top_n={ORGAN_MARKERS_TOP_N}", f"organs/{s}/markers.json", optional=True
        )
        w.get(
            f"{base}/composition-by?group={COMPOSITION_GROUP}",
            f"organs/{s}/composition.json",
            optional=True,
        )
        w.get(f"{base}/tf?top_n={TF_TOP_N}", f"organs/{s}/tf.json", optional=True)
        w.get(f"{base}/cci?limit={CCI_LIMIT}", f"organs/{s}/cci.json", optional=True)
        for kind in ("umap", "tf", "cci"):
            w.get(f"{base}/fig/{kind}", f"organs/{s}/fig-{kind}.json", optional=True)
        for coll in GSEA_COLLECTIONS:
            w.get(
                f"{base}/gsea?collection={coll}&top_n={GSEA_TOP_N}",
                f"organs/{s}/gsea-{coll}.json",
                optional=True,
            )
            w.get(
                f"{base}/fig/gsea?collection={coll}",
                f"organs/{s}/fig-gsea-{coll}.json",
                optional=True,
            )
    return w


def _symbol_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Gene-symbol columns (original case), first occurrence per upper-cased symbol.

    Matches the API's lookups, which compare symbols case-insensitively and keep
    the first feature when several Ensembl ids share a symbol.
    """
    out = df.copy()
    out.columns = [str(c).split("_ENSG")[0] for c in out.columns]
    return out.loc[:, ~pd.Index([c.upper() for c in out.columns]).duplicated()]


def export_expression(out: Path) -> dict[str, int]:
    """Compact per-organ expression tables for in-browser gene/signature/lookup.

    Genes expressed nowhere in the organ (all-zero mean) are listed by name only,
    since they still count as recognized vocabulary. For the rest, the fraction
    expressing is stored as uint8 (value / 255) and the mean as uint16 scaled by
    the organ's maximum (``mean_scale``), row-major, labels x genes, gzipped.
    """
    sizes: dict[str, int] = {}
    for organ in ORGANS:
        s = slug(organ)
        mean = data.expression(s, "mean")
        pct = data.expression(s, "pct")
        if mean is None or pct is None:
            continue
        mean, pct = _symbol_frame(mean), _symbol_frame(pct)
        pct = pct.reindex(columns=mean.columns)
        dense = mean.columns[(mean.to_numpy() > 0).any(axis=0)]
        dense_set = set(dense)
        zero = [g for g in mean.columns if g not in dense_set]
        mean_scale = float(mean[dense].to_numpy().max()) or 1.0
        pct_q = np.rint(pct[dense].to_numpy() * 255).clip(0, 255).astype(np.uint8)
        mean_q = np.rint(mean[dense].to_numpy() / mean_scale * 65535).clip(0, 65535)
        mean_q = mean_q.astype("<u2")

        path = out / "expr"
        path.mkdir(parents=True, exist_ok=True)
        meta = {
            "organ": organ,
            "labels": [str(x) for x in mean.index],
            "genes": [str(g) for g in dense],
            "zero_genes": zero,
            "mean_scale": mean_scale,
        }
        (path / f"{s}.json").write_text(json.dumps(meta, separators=(",", ":")))
        for name, arr in (("pct", pct_q), ("mean", mean_q)):
            blob = gzip.compress(arr.tobytes(order="C"), compresslevel=9, mtime=0)
            (path / f"{s}.{name}.bin.gz").write_bytes(blob)
            sizes[f"{s}.{name}"] = len(blob)
    return sizes


def export_all(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    w = export_api(out)
    print(f"api responses: {w.n_files} files, {w.n_bytes / 1e6:.1f} MB")
    if w.skipped:
        print(f"  skipped (no data, same 404 as the server): {len(w.skipped)}")
    sizes = export_expression(out)
    pct_total = sum(v for k, v in sizes.items() if k.endswith(".pct"))
    mean_total = sum(v for k, v in sizes.items() if k.endswith(".mean"))
    print(
        f"expression tables: pct {pct_total / 1e6:.1f} MB, mean {mean_total / 1e6:.1f} MB (gzipped)"
    )
