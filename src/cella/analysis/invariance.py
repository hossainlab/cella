"""Cross-organ invariance of discriminative cell-type identity.

For every cell type (Cell Ontology term) that CellTypist models in two or more
organs, this module asks how similar the learned discriminative weight vector
is across those organs.

Method
------
1. Per organ, take the model's ``coef_`` row for the cell type. Where several
   curated labels in one organ map to the same CL term, the rows are combined
   as a cell-count-weighted mean (approximating the pooled population).
2. For each organ pair, restrict both vectors to the genes shared by the two
   models (the models have different feature spaces; the intersection across
   all twelve is only ~722 genes, so pairwise intersections are used instead),
   L2-normalize, and take the cosine.
3. The cell type's **invariance score** is the mean over its organ pairs.

The score is calibrated against a label-shuffled null: cosines between a cell
type in one organ and a *different* cell type in another organ, computed over
the same pairwise gene spaces.
"""

from __future__ import annotations

import itertools
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_DIR = Path("data/raw/models")
PROCESSED = Path("data/processed")


def model_file(organ: str) -> Path:
    """Path to an organ's CellTypist ``.pkl``."""
    return MODEL_DIR / f"Adult_Human_{organ.replace(' ', '_')}.pkl"


@dataclass(frozen=True)
class OrganModel:
    """One organ's coefficient matrix, rows keyed by curated label."""

    organ: str
    genes: np.ndarray  # (n_genes,) gene symbols
    gene_index: dict[str, int]
    coef: np.ndarray  # (n_cell_types, n_genes)
    labels: list[str]
    label_index: dict[str, int]


def load_organ(organ: str) -> OrganModel:
    """Unpickle an organ model and expose its coefficients as plain arrays."""
    with model_file(organ).open("rb") as handle:
        payload = pickle.load(handle)  # noqa: S301 - first-party CellTypist release
    clf = payload["Model"]
    genes = np.asarray(clf.features, dtype=object)
    labels = [str(c) for c in clf.classes_]
    return OrganModel(
        organ=organ,
        genes=genes,
        gene_index={g: i for i, g in enumerate(genes)},
        coef=np.asarray(clf.coef_, dtype=np.float64),
        labels=labels,
        label_index={lab: i for i, lab in enumerate(labels)},
    )


def cell_type_vectors(
    models: dict[str, OrganModel], cell_type_organ: pd.DataFrame
) -> dict[tuple[str, str], np.ndarray]:
    """Return ``(organ, cl_id) -> weight vector`` in that organ's gene space.

    Curated labels sharing a CL term within an organ are averaged, weighted by
    cell count.
    """
    vectors: dict[tuple[str, str], np.ndarray] = {}
    grouped = cell_type_organ.groupby(["organ", "cl_id"], sort=False)
    for (organ, cl_id), rows in grouped:
        model = models[organ]
        idx = [model.label_index[lab] for lab in rows["curated_label"]]
        weights = rows["cell_count"].to_numpy(dtype=np.float64)
        weights = weights / weights.sum()
        vectors[(organ, cl_id)] = weights @ model.coef[idx, :]
    return vectors


def _shared_gene_slices(a: OrganModel, b: OrganModel) -> tuple[np.ndarray, np.ndarray]:
    """Index arrays selecting the genes shared by two models, in a common order."""
    shared = np.intersect1d(a.genes.astype(str), b.genes.astype(str))
    return (
        np.array([a.gene_index[g] for g in shared]),
        np.array([b.gene_index[g] for g in shared]),
    )


def _cosine(u: np.ndarray, v: np.ndarray) -> float:
    """Cosine similarity, 0.0 when either vector is degenerate."""
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu == 0.0 or nv == 0.0:
        return 0.0
    return float(u @ v / (nu * nv))


def pair_cosines(
    models: dict[str, OrganModel],
    vectors: dict[tuple[str, str], np.ndarray],
    organ_a: str,
    organ_b: str,
) -> tuple[pd.DataFrame, int]:
    """All cross-organ cosines between cell types of two organs.

    Returns a tidy frame with one row per ``(cl_a, cl_b)`` pair plus the size of
    the shared gene space. Rows where ``cl_a == cl_b`` are the matched signal;
    the rest form the label-shuffled null.
    """
    a, b = models[organ_a], models[organ_b]
    slice_a, slice_b = _shared_gene_slices(a, b)

    cls_a = sorted(cl for (o, cl) in vectors if o == organ_a)
    cls_b = sorted(cl for (o, cl) in vectors if o == organ_b)

    mat_a = np.vstack([vectors[(organ_a, cl)][slice_a] for cl in cls_a])
    mat_b = np.vstack([vectors[(organ_b, cl)][slice_b] for cl in cls_b])
    mat_a /= np.clip(np.linalg.norm(mat_a, axis=1, keepdims=True), 1e-12, None)
    mat_b /= np.clip(np.linalg.norm(mat_b, axis=1, keepdims=True), 1e-12, None)
    cos = mat_a @ mat_b.T

    frame = pd.DataFrame(
        {
            "organ_a": organ_a,
            "organ_b": organ_b,
            "cl_a": np.repeat(cls_a, len(cls_b)),
            "cl_b": np.tile(cls_b, len(cls_a)),
            "cosine": cos.ravel(),
            "n_shared_genes": len(slice_a),
        }
    )
    return frame, len(slice_a)


def core_fraction(
    models: dict[str, OrganModel],
    vectors: dict[tuple[str, str], np.ndarray],
    cl_id: str,
    organs: list[str],
    top_k: int = 50,
) -> tuple[float, list[str]]:
    """Fraction of a cell type's top-``k`` positive genes shared by every organ.

    Each organ's top-``k`` is taken within the genes common to all the listed
    organs, so the sets are directly comparable.
    """
    common = set.intersection(*[set(models[o].genes.astype(str)) for o in organs])
    top_sets: list[set[str]] = []
    for organ in organs:
        model = models[organ]
        idx = np.array([model.gene_index[g] for g in common])
        names = model.genes.astype(str)[idx]
        coefs = vectors[(organ, cl_id)][idx]
        order = np.argsort(-coefs)[:top_k]
        top_sets.append(set(names[order]))
    core = set.intersection(*top_sets)
    return len(core) / top_k, sorted(core)


def mean_pairwise_jaccard(
    models: dict[str, OrganModel],
    vectors: dict[tuple[str, str], np.ndarray],
    cl_id: str,
    organs: list[str],
    top_k: int = 50,
) -> float:
    """Mean Jaccard overlap of a cell type's top-``k`` positive genes across organ pairs.

    Unlike :func:`core_fraction`, each pair is scored in its own shared gene
    space, so the measure does not collapse as the number of organs grows.
    """
    scores: list[float] = []
    for organ_a, organ_b in itertools.combinations(organs, 2):
        a, b = models[organ_a], models[organ_b]
        slice_a, slice_b = _shared_gene_slices(a, b)
        names = a.genes.astype(str)[slice_a]
        top_a = set(names[np.argsort(-vectors[(organ_a, cl_id)][slice_a])[:top_k]])
        top_b = set(names[np.argsort(-vectors[(organ_b, cl_id)][slice_b])[:top_k]])
        union = top_a | top_b
        scores.append(len(top_a & top_b) / len(union) if union else 0.0)
    return float(np.mean(scores)) if scores else float("nan")


def low_granularity_terms(cl_ids: list[str]) -> set[str]:
    """CL terms in ``cl_ids`` that are ancestors of another term in the same set.

    Such a term was used as an annotation in some organs while its own subtypes
    were annotated separately elsewhere, so a weight vector built from it mixes
    populations of differing specificity. These are reported separately rather
    than read as biological plasticity.
    """
    from cellxgene_ontology_guide.ontology_parser import OntologyParser

    parser = OntologyParser()
    present = set(cl_ids)
    coarse: set[str] = set()
    for cl_id in present:
        try:
            ancestors = set(parser.get_term_ancestors(cl_id))
        except (KeyError, ValueError):
            continue
        coarse |= ancestors & present
    return coarse


#: Lineage buckets, tried in order; first matching CL ancestor wins.
LINEAGE_ANCESTORS: tuple[tuple[str, str], ...] = (
    ("CL:0000542", "Lymphoid"),  # lymphocyte
    ("CL:0000764", "Erythroid/Mega"),  # erythroid lineage cell
    ("CL:0000556", "Erythroid/Mega"),  # megakaryocyte
    ("CL:0000763", "Myeloid"),  # myeloid cell (after the erythroid/mega branches)
    ("CL:0000113", "Myeloid"),  # mononuclear phagocyte
    ("CL:0000451", "Myeloid"),  # dendritic cell
    ("CL:0000115", "Endothelial"),  # endothelial cell
    ("CL:0000134", "Mesenchymal/Stromal"),  # mesenchymal stem cell
    ("CL:0002320", "Mesenchymal/Stromal"),  # connective tissue cell
    ("CL:0000187", "Muscle/Mural"),  # muscle cell
    ("CL:0000066", "Epithelial"),  # epithelial cell
    ("CL:0002319", "Neural"),  # neural cell
)


def assign_lineages(cl_ids: list[str]) -> dict[str, str]:
    """Bucket CL terms into broad lineages using their ontology ancestors."""
    from cellxgene_ontology_guide.ontology_parser import OntologyParser

    parser = OntologyParser()
    out: dict[str, str] = {}
    for cl_id in cl_ids:
        try:
            lineage_set = set(parser.get_term_ancestors(cl_id)) | {cl_id}
        except (KeyError, ValueError):
            lineage_set = {cl_id}
        out[cl_id] = next(
            (name for anc, name in LINEAGE_ANCESTORS if anc in lineage_set), "Other"
        )
    return out
