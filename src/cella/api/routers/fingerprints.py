"""Cross-Organ Fingerprint Explorer.

For a cell type, the top positive/negative classifier weights per organ, for
side-by-side heatmap/radar comparison, plus a single gene's weight across all
organs. See docs/CONCEPT.md §7.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from cella.api import data
from cella.api.schemas import (
    Fingerprint,
    FingerprintCell,
    FingerprintGene,
    GeneAcrossOrgans,
    GeneOrganWeight,
    GeneWeight,
    OrganMarkers,
)

router = APIRouter(prefix="/fingerprints", tags=["fingerprint-explorer"])


def _lookup_label(cl_id: str) -> str:
    reg = data.registry()
    row = reg[reg["cl_id"] == cl_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"unknown cl_id: {cl_id}")
    return str(row.iloc[0]["ontology_label"])


@router.get("/{cl_id}", response_model=Fingerprint)
def fingerprint(
    cl_id: str,
    top_n: int = Query(10, ge=1, le=25, description="Genes per direction per organ."),
) -> Fingerprint:
    """Per-organ discriminative fingerprints (signed +/- weights) for one cell type."""
    ontology_label = _lookup_label(cl_id)

    mk = data.markers()
    mk = mk[mk["cl_id"] == cl_id]
    if mk.empty:
        raise HTTPException(status_code=404, detail=f"no markers for cl_id: {cl_id}")

    organs = sorted(mk["organ"].unique())
    per_organ: list[OrganMarkers] = []
    # gene -> organ -> (coef, rank, direction), keeping the strongest |coef| per cell.
    pivot: dict[str, dict[str, FingerprintCell]] = {}

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

        pos, neg = _top("positive"), _top("negative")
        per_organ.append(OrganMarkers(organ=organ, positive=pos, negative=neg))

        for direction, ranked in (("positive", pos), ("negative", neg)):
            for g in ranked:
                cell = FingerprintCell(
                    organ=organ, coef=g.coef, rank=g.rank, direction=direction
                )
                by_organ = pivot.setdefault(g.gene, {})
                prev = by_organ.get(organ)
                if prev is None or abs(cell.coef) > abs(prev.coef):
                    by_organ[organ] = cell

    genes = [
        FingerprintGene(
            gene=gene,
            n_organs=len(cells),
            max_abs=max(abs(c.coef) for c in cells.values()),
            cells=sorted(cells.values(), key=lambda c: organs.index(c.organ)),
        )
        for gene, cells in pivot.items()
    ]
    # Shared genes (defining in many organs) first; strongest weight breaks ties.
    genes.sort(key=lambda g: (-g.n_organs, -g.max_abs, g.gene))

    return Fingerprint(
        cl_id=cl_id,
        ontology_label=ontology_label,
        organs=organs,
        per_organ=per_organ,
        genes=genes,
    )


@router.get("/{cl_id}/gene/{gene}", response_model=GeneAcrossOrgans)
def gene_across_organs(cl_id: str, gene: str) -> GeneAcrossOrgans:
    """One gene's signed weight for this cell type across every organ it appears in.

    Organs where the gene is not among the stored top-N discriminative markers are
    reported as ``absent_in`` (coverage is limited to the precomputed top-N).
    """
    ontology_label = _lookup_label(cl_id)

    mk = data.markers()
    mk = mk[mk["cl_id"] == cl_id]
    if mk.empty:
        raise HTTPException(status_code=404, detail=f"no markers for cl_id: {cl_id}")

    organs = sorted(mk["organ"].unique())
    hits = mk[mk["gene"].str.upper() == gene.upper()]

    present: list[GeneOrganWeight] = []
    present_organs: set[str] = set()
    for organ in organs:
        row = hits[hits["organ"] == organ]
        if row.empty:
            continue
        # Strongest |coef| if the gene appears via multiple curated labels.
        r = row.loc[row["coef"].abs().idxmax()]
        present.append(
            GeneOrganWeight(
                organ=organ,
                coef=float(r["coef"]),
                rank=int(r["rank"]),
                direction=str(r["direction"]),
            )
        )
        present_organs.add(organ)

    present.sort(key=lambda w: -abs(w.coef))
    return GeneAcrossOrgans(
        cl_id=cl_id,
        ontology_label=ontology_label,
        gene=gene,
        present_in=present,
        absent_in=[o for o in organs if o not in present_organs],
    )
