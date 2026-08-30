"""Shared cell-type lookups (search, detail) used by every tool."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from cella.api import data
from cella.api.schemas import CellTypeDetail, CellTypeSummary, OrganPresence

router = APIRouter(prefix="/cell-types", tags=["cell-types"])


@router.get("", response_model=list[CellTypeSummary])
def search_cell_types(
    q: str | None = Query(None, description="Substring of ontology label or CL id."),
    min_organs: int = Query(1, ge=1, description="Only types present in >= this many organs."),
    limit: int = Query(50, ge=1, le=500),
) -> list[CellTypeSummary]:
    """Search harmonized cross-organ cell types."""
    reg = data.registry()
    if q:
        mask = reg["ontology_label"].str.contains(q, case=False, na=False) | reg[
            "cl_id"
        ].str.contains(q, case=False, na=False)
        reg = reg[mask]
    reg = reg[reg["n_organs"] >= min_organs].head(limit)
    return [CellTypeSummary(**r) for r in reg.to_dict("records")]


@router.get("/{cl_id}", response_model=CellTypeDetail)
def get_cell_type(cl_id: str) -> CellTypeDetail:
    """Detail for one cell type: organs it appears in, aliases, per-organ counts."""
    reg = data.registry()
    row = reg[reg["cl_id"] == cl_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"unknown cl_id: {cl_id}")
    rec = row.iloc[0]

    cto = data.cell_type_organ()
    presence = cto[cto["cl_id"] == cl_id].sort_values("cell_count", ascending=False)
    return CellTypeDetail(
        cl_id=rec["cl_id"],
        ontology_label=rec["ontology_label"],
        n_organs=int(rec["n_organs"]),
        total_cells=int(rec["total_cells"]),
        organs=[o.strip() for o in rec["organs"].split(",")],
        aliases=[a.strip() for a in rec["aliases"].split("|")],
        presence=[
            OrganPresence(
                organ=p["organ"],
                curated_label=p["curated_label"],
                cell_count=int(p["cell_count"]),
            )
            for p in presence.to_dict("records")
        ],
    )
