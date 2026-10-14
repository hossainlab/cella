"""Relationship Graph Explorer.

Serves filtered subgraphs of the precomputed cross-tissue relationship graph:
nodes (cell types, sized by cell count) and edges (transcriptomic similarity),
filterable by organ. Clicking an edge returns the genes the two types share.
See docs/CONCEPT.md §7 (v1 uses the similarity-graph fallback, §5.5).
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from cella.api import data
from cella.api.schemas import (
    EdgeDetail,
    GraphEdge,
    GraphNode,
    RelationshipGraph,
    SharedEdgeGene,
)

router = APIRouter(prefix="/graph", tags=["graph-explorer"])


def _node(row: pd.Series) -> GraphNode:
    return GraphNode(
        cl_id=row["cl_id"],
        label=row["label"],
        n_organs=int(row["n_organs"]),
        total_cells=int(row["total_cells"]),
        primary_organ=str(row["primary_organ"]),
        x=float(row["x"]),
        y=float(row["y"]),
    )


@router.get("", response_model=RelationshipGraph)
def subgraph(
    organ: str | None = Query(None, description="Limit to types present in this organ."),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="Edge similarity floor."),
) -> RelationshipGraph:
    """Nodes + edges for the requested slice of the relationship graph."""
    nodes_df = data.graph_nodes()
    edges_df = data.graph_edges()
    all_organs = sorted(o for o in nodes_df["primary_organ"].unique() if o)
    n_total = len(nodes_df)

    if organ is not None:
        # Types present in this organ: primary there, or sharing a curated label there.
        cto = data.cell_type_organ()
        in_organ = set(cto[cto["organ"] == organ]["cl_id"].dropna())
        nodes_df = nodes_df[nodes_df["cl_id"].isin(in_organ)]
        if nodes_df.empty:
            raise HTTPException(status_code=404, detail=f"no cell types in organ: {organ}")

    keep = set(nodes_df["cl_id"])
    edges_df = edges_df[
        edges_df["source"].isin(keep)
        & edges_df["target"].isin(keep)
        & (edges_df["similarity"] >= min_similarity)
    ]

    return RelationshipGraph(
        organs=all_organs,
        nodes=[_node(r) for _, r in nodes_df.iterrows()],
        edges=[
            GraphEdge(source=e["source"], target=e["target"], similarity=float(e["similarity"]))
            for _, e in edges_df.iterrows()
        ],
        n_total_nodes=n_total,
    )


def _top_positive(cl_id: str) -> dict[str, float]:
    """Strongest positive marker weight per gene for a harmonized type, across organs."""
    mk = data.markers()
    sub = mk[(mk["cl_id"] == cl_id) & (mk["direction"] == "positive")]
    if sub.empty:
        return {}
    return sub.groupby("gene")["coef"].max().to_dict()


@router.get("/edge/{source_id}/{target_id}", response_model=EdgeDetail)
def edge_detail(
    source_id: str,
    target_id: str,
    top_n: int = Query(15, ge=1, le=50, description="Max shared genes to return."),
) -> EdgeDetail:
    """What two cell types share: the discriminative genes defining both (edge basis)."""
    nodes_df = data.graph_nodes()

    def _lookup(cl_id: str) -> pd.Series:
        row = nodes_df[nodes_df["cl_id"] == cl_id]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"unknown node: {cl_id}")
        return row.iloc[0]

    src_row, tgt_row = _lookup(source_id), _lookup(target_id)

    edges_df = data.graph_edges()
    a, b = sorted((source_id, target_id))
    edge = edges_df[(edges_df["source"] == a) & (edges_df["target"] == b)]
    similarity = float(edge.iloc[0]["similarity"]) if not edge.empty else 0.0

    src_w, tgt_w = _top_positive(source_id), _top_positive(target_id)
    shared = set(src_w) & set(tgt_w)
    # Rank shared genes by the weaker of the two weights (strong in *both* types);
    # ties break on the gene name so the order does not depend on set iteration.
    ranked = sorted(shared, key=lambda g: (-min(src_w[g], tgt_w[g]), g))[:top_n]

    return EdgeDetail(
        source=_node(src_row),
        target=_node(tgt_row),
        similarity=similarity,
        shared_genes=[
            SharedEdgeGene(gene=g, source_coef=src_w[g], target_coef=tgt_w[g])
            for g in ranked
        ],
    )
