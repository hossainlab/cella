"""P4 — Cross-tissue relationship graph (highest-risk step).

The CellTypist v2.0 relationship graph exists in a paper, not as a downloadable
artifact. The faithful reproduction (CellHint / predictive-clustering-tree on the
harmonized labels) is deferred; v1 ships the **documented similarity-graph
fallback** from docs/CONCEPT.md §5.5 / §10: edges are the cosine similarity
between harmonized cell types' classifier-weight vectors.

Emits two artifacts into ``settings.processed_dir``:

    graph_nodes.parquet   cl_id, label, n_organs, total_cells, primary_organ, x, y
    graph_edges.parquet   source, target, similarity  (undirected, cl_id keys)

Node coordinates are a deterministic spring layout so the frontend can render a
stable graph without a client-side physics sim.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cella.core.config import ORGANS, settings

# A weight-vector cosine below this is treated as "unrelated" (no edge).
_MIN_SIMILARITY = 0.15
# Keep at most this many strongest neighbours per node (keeps the graph legible).
_TOP_K = 6


def _slug(organ: str) -> str:
    return organ.replace(" ", "_")


def _aggregate_vectors() -> pd.DataFrame:
    """One weight vector per harmonized cell type (cl_id), over the union gene space.

    A harmonized type can appear in several organs under several curated labels;
    its vector is the mean of those organ-level weight rows, aligned on the union
    of all genes (missing genes = 0).
    """
    cto = pd.read_parquet(settings.processed_dir / "cell_type_organ.parquet")
    frames: list[pd.DataFrame] = []
    for organ in ORGANS:
        path = settings.processed_dir / "weights" / f"{_slug(organ)}.parquet"
        if not path.exists():
            continue
        w = pd.read_parquet(path)  # index = curated_label, columns = genes
        label_to_cl = (
            cto[cto["organ"] == organ]
            .dropna(subset=["cl_id"])
            .set_index("curated_label")["cl_id"]
        )
        present = w.index.intersection(label_to_cl.index)
        if present.empty:
            continue
        sub = w.loc[present].copy()
        sub.insert(0, "cl_id", label_to_cl.loc[present].to_numpy())
        frames.append(sub)

    if not frames:
        raise RuntimeError(
            "no weight matrices found; run `cella build` before `cella graph`"
        )

    # Outer-join on the union of gene columns, then average per harmonized type.
    combined = pd.concat(frames, axis=0)
    combined = combined.groupby("cl_id").mean().fillna(0.0)
    return combined


def _cosine(matrix: np.ndarray) -> np.ndarray:
    from sklearn.metrics.pairwise import cosine_similarity

    return cosine_similarity(matrix)


def _edges(sim: np.ndarray, cl_ids: list[str]) -> pd.DataFrame:
    """Undirected top-k edges above the similarity floor, strongest kept on ties."""
    kept: dict[tuple[str, str], float] = {}
    n = len(cl_ids)
    for i in range(n):
        order = np.argsort(sim[i])[::-1]
        added = 0
        for j in order:
            if j == i:
                continue
            s = float(sim[i, j])
            if s < _MIN_SIMILARITY or added >= _TOP_K:
                break
            a, b = sorted((cl_ids[i], cl_ids[j]))
            key = (a, b)
            if s > kept.get(key, -1.0):
                kept[key] = s
            added += 1
    return pd.DataFrame(
        ({"source": a, "target": b, "similarity": s} for (a, b), s in kept.items())
    )


def _layout(cl_ids: list[str], edges: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Deterministic spring layout; edge similarity pulls related nodes together."""
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(cl_ids)
    for r in edges.itertuples(index=False):
        g.add_edge(r.source, r.target, weight=r.similarity)
    pos = nx.spring_layout(g, weight="weight", seed=42, k=0.35, iterations=200)
    return {node: (float(xy[0]), float(xy[1])) for node, xy in pos.items()}


def build_similarity_graph_fallback() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fallback graph: edges from cosine distance between cell-type weight vectors."""
    out = settings.processed_dir
    registry = pd.read_parquet(out / "registry.parquet").set_index("cl_id")
    cto = pd.read_parquet(out / "cell_type_organ.parquet")

    vectors = _aggregate_vectors()
    # Restrict to harmonized types that are actually in the registry, stable order.
    cl_ids = [c for c in vectors.index if c in registry.index]
    vectors = vectors.loc[cl_ids]

    sim = _cosine(vectors.to_numpy())
    edges = _edges(sim, cl_ids)
    pos = _layout(cl_ids, edges)

    # primary_organ = the organ contributing the most cells to each harmonized type.
    primary = (
        cto.dropna(subset=["cl_id"])
        .sort_values("cell_count", ascending=False)
        .drop_duplicates("cl_id")
        .set_index("cl_id")["organ"]
    )

    nodes = pd.DataFrame(
        {
            "cl_id": cl_ids,
            "label": registry.loc[cl_ids, "ontology_label"].to_numpy(),
            "n_organs": registry.loc[cl_ids, "n_organs"].to_numpy(),
            "total_cells": registry.loc[cl_ids, "total_cells"].to_numpy(),
            "primary_organ": [primary.get(c, "") for c in cl_ids],
            "x": [pos[c][0] for c in cl_ids],
            "y": [pos[c][1] for c in cl_ids],
        }
    )

    nodes.to_parquet(out / "graph_nodes.parquet")
    edges.to_parquet(out / "graph_edges.parquet")
    return nodes, edges


def build_relationship_graph() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Emit graph nodes + weighted edges.

    v1 uses the documented transcriptomic-similarity fallback; the faithful
    CellHint recompute is future work (docs/CONCEPT.md §5.5).
    """
    return build_similarity_graph_fallback()
