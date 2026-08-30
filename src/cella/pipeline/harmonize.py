"""P1 - Harmonization.

Assemble the canonical cross-organ cell-type registry from the per-organ
metadata. Cell Ontology ID (``cl_id``) is the join key, so the same cell type in
different organs collapses to one node; organ-specific curated labels are kept as
aliases. See docs/CONCEPT.md §5.4, §6.
"""

from __future__ import annotations

import pandas as pd

from cella.core.config import ORGANS
from cella.pipeline.extract import extract_metadata


def build_long_metadata(organs: tuple[str, ...] = ORGANS) -> pd.DataFrame:
    """Per (organ, curated cell type) rows: counts + ontology label + CL id.

    This is the ``CELL_TYPE_ORGAN`` table (the ~399 organ-level rows).
    """
    frames = [extract_metadata(organ) for organ in organs]
    long = pd.concat(frames, ignore_index=True)
    return long.rename(columns={"label": "curated_label"})


def build_registry(long: pd.DataFrame | None = None) -> pd.DataFrame:
    """Collapse the long table to canonical cross-organ cell types, keyed by CL id.

    This is the ``CELL_TYPE`` table (the ~145 harmonized nodes).
    """
    if long is None:
        long = build_long_metadata()
    keyed = long.dropna(subset=["cl_id"])
    registry = (
        keyed.groupby("cl_id", as_index=False)
        .agg(
            ontology_label=("ontology_label", "first"),
            n_organs=("organ", "nunique"),
            total_cells=("cell_count", "sum"),
            organs=("organ", lambda s: sorted(set(s))),
            aliases=("curated_label", lambda s: sorted(set(s))),
        )
        .sort_values("total_cells", ascending=False, ignore_index=True)
    )
    return registry
