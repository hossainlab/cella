"""Reverse lookup — "paste your markers, which cell type do they define?".

The inverse of the Marker Atlas: given a gene signature, score it against every
organ model's discriminative weight matrix and return the best-matching cell
types. A weak best score flags a possible novel / uncharacterized state.
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

# A mean discriminative weight below this is treated as "no real match".
_MIN_SCORE = 0.10
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
        try:
            w = data.weights(_slug(org))
        except ArtifactsNotBuilt:
            continue
        # Case-insensitive column match: uppercased gene -> real column name.
        col_by_upper = {c.upper(): c for c in w.columns}
        present = [col_by_upper[g] for g in query if g in col_by_upper]
        if not present:
            continue
        matched.update(g for g in query if g in col_by_upper)

        sub = w[present]  # cell types x matched genes
        scores = sub.mean(axis=1)  # mean discriminative weight per cell type
        for curated_label, score in scores.items():
            row = sub.loc[curated_label]
            top = row.sort_values(ascending=False).head(5)
            cl_id, onto = label_map.get((org, str(curated_label)), (None, str(curated_label)))
            hits.append(
                SignatureHit(
                    cl_id=cl_id,
                    ontology_label=onto,
                    curated_label=str(curated_label),
                    organ=org,
                    score=float(score),
                    n_matched=len(present),
                    top_genes=[SignatureGene(gene=str(g), coef=float(c)) for g, c in top.items()],
                )
            )

    if not hits:
        return ReverseLookup(
            query_genes=query,
            matched_genes=[],
            unknown_genes=query,
            hits=[],
            is_confident=False,
            note="None of these genes are in the organ models' vocabularies.",
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    top_hits = hits[:limit]
    best = top_hits[0]
    is_confident = best.score >= _MIN_SCORE and best.n_matched >= min(2, len(matched))
    unknown = [g for g in query if g not in matched]

    if is_confident:
        note = (
            f"Best match: {best.ontology_label} in {best.organ} "
            f"(mean weight {best.score:.2f} over {best.n_matched} of {len(query)} genes)."
        )
    else:
        note = (
            "No strong match — these genes do not collectively define any single "
            "cell type in the atlas. Could be a mixed, rare, or novel state, or too "
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
