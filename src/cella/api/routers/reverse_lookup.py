"""Reverse lookup — "paste your markers, which cell type do they define?".

The inverse of the Marker Atlas: given a gene signature, rank every atlas cell
type by the mean fraction of its cells that express the query genes. A weak or
ambiguous best match flags a possible novel / uncharacterized state.

Scoring by expression rather than by classifier weight is a benchmarked choice
(``scripts/lookup_benchmark.py``): on external marker sets held out from method
selection (Tabula Sapiens, Azimuth, PanglaoDB), mean fraction-expressing ranks
the right cell type first for 40% of queries vs 17% for mean classifier weight.
Weights stay in each hit as evidence of which query genes are discriminative.
See docs/CONCEPT.md §11 (v1.1 candidate).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from cella.api import data
from cella.api.data import ArtifactsNotBuilt
from cella.api.schemas import ReverseLookup, SignatureGene, SignatureHit
from cella.core.config import ORGANS

router = APIRouter(prefix="/reverse-lookup", tags=["reverse-lookup"])

# Confidence rule, calibrated on the benchmark's dev library (CellMarker) only:
# the top hit must be expressed (mean fraction >= _MIN_SCORE) and lead the best
# hit of any *other* cell type by >= _MIN_MARGIN of its score. On held-out
# libraries this splits top-1 precision 0.62 (confident) vs 0.33 (not).
_MIN_SCORE = 0.30
_MIN_MARGIN = 0.10
_MAX_GENES = 200


def _slug(organ: str) -> str:
    return organ.replace(" ", "_")


def _parse_genes(raw: str) -> list[str]:
    """Split a pasted signature on commas/whitespace/newlines; dedupe, keep order."""
    seen: dict[str, None] = {}
    for tok in re.split(r"[\s,;]+", raw.strip()):
        g = tok.strip().upper()
        if g:
            seen.setdefault(g, None)
    return list(seen)


@router.get("", response_model=ReverseLookup)
def reverse_lookup(
    genes: str = Query(..., description="Gene signature: comma/space/newline separated."),
    organ: str | None = Query(None, description="Restrict scoring to one organ."),
    limit: int = Query(15, ge=1, le=50, description="Max cell-type hits to return."),
) -> ReverseLookup:
    """Rank cell types by how strongly the signature discriminates them."""
    query = _parse_genes(genes)
    if not query:
        raise HTTPException(status_code=400, detail="no genes provided")
    if len(query) > _MAX_GENES:
        raise HTTPException(status_code=400, detail=f"too many genes (max {_MAX_GENES})")

    organs = [organ] if organ else list(ORGANS)
    # (organ, curated_label) -> (cl_id, ontology_label) for harmonizing hits.
    cto = data.cell_type_organ()
    label_map: dict[tuple[str, str], tuple[str | None, str]] = {}
    for r in cto.to_dict("records"):
        cl = r["cl_id"] if isinstance(r["cl_id"], str) else None
        onto = r["ontology_label"] if isinstance(r["ontology_label"], str) else r["curated_label"]
        label_map[(r["organ"], r["curated_label"])] = (cl, onto)

    matched: set[str] = set()
    hits: list[SignatureHit] = []

    for org in organs:
        pct = data.pct_by_symbol(_slug(org))
        if pct is None:
            continue
        present = [g for g in query if g in pct.columns]
        if not present:
            continue
        matched.update(present)
        try:
            w = data.weights(_slug(org))
            coef_by_upper = {c.upper(): c for c in w.columns}
        except ArtifactsNotBuilt:
            w, coef_by_upper = None, {}

        sub = pct[present]  # cell types x matched genes
        scores = sub.mean(axis=1)  # mean fraction of cells expressing the query
        for curated_label, score in scores.items():
            label = str(curated_label)
            top = sub.loc[curated_label].sort_values(ascending=False).head(5)
            genes = []
            for g, frac in top.items():
                col = coef_by_upper.get(g)
                coef = (
                    float(w.at[curated_label, col])
                    if w is not None and col is not None and curated_label in w.index
                    else None
                )
                genes.append(SignatureGene(gene=str(g), pct=float(frac), coef=coef))
            cl_id, onto = label_map.get((org, label), (None, label))
            hits.append(
                SignatureHit(
                    cl_id=cl_id,
                    ontology_label=onto,
                    curated_label=label,
                    organ=org,
                    score=float(score),
                    n_matched=len(present),
                    top_genes=genes,
                )
            )

    if not hits:
        return ReverseLookup(
            query_genes=query,
            matched_genes=[],
            unknown_genes=query,
            hits=[],
            is_confident=False,
            note="None of these genes are in the atlas gene vocabulary.",
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    top_hits = hits[:limit]
    best = top_hits[0]
    # The same cell type in another organ is not a competing answer.
    best_key = best.cl_id or best.ontology_label
    runner_up = next((h.score for h in hits if (h.cl_id or h.ontology_label) != best_key), 0.0)
    margin = (best.score - runner_up) / best.score if best.score > 0 else 0.0
    is_confident = (
        best.score >= _MIN_SCORE
        and margin >= _MIN_MARGIN
        and best.n_matched >= min(2, len(matched))
    )
    unknown = [g for g in query if g not in matched]

    if is_confident:
        note = (
            f"Best match: {best.ontology_label} in {best.organ} "
            f"({best.score:.0%} of its cells express the query genes on average, "
            f"{best.n_matched} of {len(query)} genes recognized; "
            f"{margin:.0%} ahead of the next cell type)."
        )
    else:
        note = (
            "No clear match — no single cell type expresses these genes markedly "
            "more than the others. Could be a mixed, rare, or novel state, or too "
            "few genes recognized."
        )

    return ReverseLookup(
        query_genes=query,
        matched_genes=[g for g in query if g in matched],
        unknown_genes=unknown,
        hits=top_hits,
        is_confident=is_confident,
        note=note,
    )
