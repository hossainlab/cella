"""P1 - Cell Ontology ID enrichment.

The atlas obs carries Cell Ontology *labels* (``cell_type``) but no ``CL:`` IDs.
This module recovers the IDs with ``cellxgene-ontology-guide`` (the same CL
release CELLxGENE curates against), giving each harmonized cell type a stable,
language-independent ID and a handle into the Cell Ontology graph.

Resolution order per label: exact label -> synonym -> manual override. Across the
12-organ atlas this maps 145/145 unique labels. See docs/CONCEPT.md §5.4.
"""

from __future__ import annotations

from functools import lru_cache

from cellxgene_ontology_guide.ontology_parser import OntologyParser

# CELLxGENE descriptive labels that don't match a CL label or synonym exactly.
MANUAL_OVERRIDES: dict[str, str] = {
    "BEST4+ intestinal epithelial cell, human": "CL:4030026",  # BEST4+ enterocyte
}


@lru_cache(maxsize=1)
def _parser() -> OntologyParser:
    return OntologyParser()


@lru_cache(maxsize=1)
def _synonym_index() -> dict[str, str]:
    """Lower-cased {label or synonym -> CL id} over the whole CL ontology."""
    op = _parser()
    index: dict[str, str] = {}
    for label, cid in op.get_term_label_to_id_map("CL").items():
        index[label.lower()] = cid
        for syn in op.get_term_synonyms(cid) or []:
            index.setdefault(syn.lower(), cid)
    return index


def label_to_cl_id(label: str) -> str | None:
    """Map a Cell Ontology label to its CL id, or None if unresolved."""
    op = _parser()
    try:
        cid = op.get_term_id_by_label(label, "CL")
    except (KeyError, ValueError):
        cid = None
    if cid:
        return cid
    cid = _synonym_index().get(label.lower())
    if cid:
        return cid
    return MANUAL_OVERRIDES.get(label)


def map_labels(labels: list[str]) -> dict[str, str | None]:
    """Map many ontology labels to CL ids in one call."""
    return {label: label_to_cl_id(label) for label in labels}
