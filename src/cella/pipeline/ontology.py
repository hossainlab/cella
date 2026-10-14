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


def close_relatives(
    cl_ids: list[str], max_parent_children: int = 3, max_descendants: int = 5
) -> dict[str, set[str]]:
    """For each term, the other terms in ``cl_ids`` that are close ontology relatives.

    A parent counts only if it is specific (an ancestor of at most
    ``max_parent_children`` terms in the set), so "leukocyte" is never a close
    relative. Children count only if the term itself is specific (at most
    ``max_descendants`` descendants in the set), so "cell" is close to nothing.
    Used to tell "two subtypes of the same thing" apart from genuinely different
    cell types, e.g. when judging whether a reverse-lookup hit is ambiguous.
    """
    op = _parser()
    present = set(cl_ids)
    ancestors: dict[str, set[str]] = {}
    for cid in present:
        try:
            ancestors[cid] = set(op.get_term_ancestors(cid)) & present
        except (KeyError, ValueError):
            ancestors[cid] = set()
    n_desc = {t: sum(t in ancestors[o] for o in present) for t in present}
    out: dict[str, set[str]] = {}
    for t in present:
        rel = {a for a in ancestors[t] if n_desc[a] <= max_parent_children}
        if n_desc[t] <= max_descendants:
            rel |= {o for o in present if t in ancestors[o]}
        out[t] = rel
    return out
