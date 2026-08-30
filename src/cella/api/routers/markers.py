"""Discriminative Marker Atlas - "what defines a cell type".

For a cell type (by CL id), the top discriminative genes per organ, plus the
consensus set (discriminative in every organ it appears in - the universal core
identity) and organ-specific genes (tissue-adapted identity). See docs/CONCEPT.md §7.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from cella.api import data
from cella.api.schemas import GeneWeight, MarkerAtlas, OrganMarkers, SharedGene

router = APIRouter(prefix="/markers", tags=["marker-atlas"])


@router.get("/{cl_id}", response_model=MarkerAtlas)
def marker_atlas(
    cl_id: str,
    top_n: int = Query(10, ge=1, le=25, description="Genes per direction per organ."),
) -> MarkerAtlas:
    """Per-organ markers + consensus (universal) and organ-specific (tissue-adapted) sets."""
    reg = data.registry()
    row = reg[reg["cl_id"] == cl_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"unknown cl_id: {cl_id}")
    ontology_label = str(row.iloc[0]["ontology_label"])

    mk = data.markers()
    mk = mk[mk["cl_id"] == cl_id]
    if mk.empty:
        raise HTTPException(status_code=404, detail=f"no markers for cl_id: {cl_id}")

    organs = sorted(mk["organ"].unique())
    per_organ: list[OrganMarkers] = []
    positive_by_organ: dict[str, set[str]] = {}

    for organ in organs:
        om = mk[mk["organ"] == organ]

        def _top(direction: str, frame=om) -> list[GeneWeight]:
            sel = (
                frame[frame["direction"] == direction]
                .sort_values("rank")
                .drop_duplicates("gene")
                .head(top_n)
            )
            return [
                GeneWeight(gene=r["gene"], coef=float(r["coef"]), rank=int(r["rank"]))
                for r in sel.to_dict("records")
            ]

        pos = _top("positive")
        per_organ.append(OrganMarkers(organ=organ, positive=pos, negative=_top("negative")))
        positive_by_organ[organ] = {g.gene for g in pos}

    # Count, for each gene, how many organs it is a top marker in.
    gene_organ_count: dict[str, int] = {}
    for genes in positive_by_organ.values():
        for g in genes:
            gene_organ_count[g] = gene_organ_count.get(g, 0) + 1

    n_organs = len(organs)
    # Shared = top marker in >=2 organs (graded), most-shared first.
    shared = sorted(
        (SharedGene(gene=g, n_organs=c) for g, c in gene_organ_count.items() if c >= 2),
        key=lambda s: (-s.n_organs, s.gene),
    )
    # Consensus = the strict subset present in every organ.
    consensus = sorted(g for g, c in gene_organ_count.items() if c == n_organs)
    # Organ-specific = top marker in exactly one organ.
    organ_specific: dict[str, list[str]] = {
        organ: sorted(g for g in genes if gene_organ_count[g] == 1)
        for organ, genes in positive_by_organ.items()
    }

    return MarkerAtlas(
        cl_id=cl_id,
        ontology_label=ontology_label,
        organs=organs,
        per_organ=per_organ,
        shared_genes=shared,
        consensus_genes=consensus,
        organ_specific=organ_specific,
    )
