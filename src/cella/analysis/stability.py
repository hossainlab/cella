"""Replicate stability of CellTypist classifier coefficients.

The invariance analysis (:mod:`cella.analysis.invariance`) reports that some
cell types have a low cross-organ cosine. That is only evidence of biological
organ adaptation if the coefficients are themselves reproducible: an unstable
beta vector would score low across organs for purely numerical reasons.

This module retrains each organ's classifier several times on resampled cells
and measures, per cell type, the mean pairwise cosine between replicate
coefficient vectors. That value is the **ceiling** the cross-organ cosine
should be read against.

Protocol
--------
* Genes are fixed to the published model's feature set (``feature_selection``
  off), so the measurement isolates coefficient stability rather than
  feature-selection churn.
* Training uses ``celltypist.train`` with its defaults, i.e. the same code path
  that produced the published models.
* Replicates use **disjoint, equally sized** folds: a cell type with at least
  ``CELLS_PER_TYPE * N_REPLICATES`` cells contributes ``CELLS_PER_TYPE`` cells
  to each replicate, and no cell is reused between replicates. This matters.
  An overlapping draw (say 80% of whatever is available) makes rare cell types
  look *more* stable than abundant ones, because their replicates are built
  from nearly the same cells - that measures draw overlap, not stability.
  Equal fold sizes also hold the training set size identical across cell
  types, so stability cannot be confounded by abundance.
* Cell types with too few cells for disjoint folds still take part in training
  - the one-vs-rest fit needs them - but they contribute all their cells to
  every replicate (adding no variance of their own) and are marked
  ``eligible=False`` rather than being scored.

Because the folds are capped and class-balanced, these replicates are not
numerically identical to the released models, which were fit on all cells with
their natural class imbalance; :func:`published_agreement` records how far
apart they sit. The measurement is a *relative* one - whether some cell types
yield less reproducible coefficients than others under a matched design.
"""

from __future__ import annotations

import pickle
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cella.analysis.invariance import model_file

COUNTS_DIR = Path("data/counts_data")
LABEL_COL = "Curated_annotation"

N_REPLICATES = 5
CELLS_PER_TYPE = 200


@dataclass(frozen=True)
class ReplicateSet:
    """Replicate coefficient vectors for one organ."""

    organ: str
    genes: np.ndarray
    labels: list[str]
    coefs: np.ndarray  # (n_replicates, n_cell_types, n_genes)
    n_pool: dict[str, int]  # cells available in the pool, per label
    eligible: dict[str, bool]  # label had enough cells for disjoint folds


def counts_file(organ: str) -> Path:
    """Path to an organ's expression matrix."""
    return COUNTS_DIR / f"{organ.replace(' ', '_')}.h5ad"


def published_features(organ: str) -> list[str]:
    """Feature set of the released model for an organ."""
    with model_file(organ).open("rb") as handle:
        payload = pickle.load(handle)  # noqa: S301 - first-party CellTypist release
    return list(payload["Model"].features)


def load_pool(organ: str, rng: np.random.Generator):
    """Read a capped, label-stratified pool of cells for one organ.

    The matrix is opened in backed mode so only the sampled rows are
    materialized; the full atlas is never held in memory.
    """
    import anndata as ad

    adata = ad.read_h5ad(counts_file(organ), backed="r")
    labels = adata.obs[LABEL_COL].to_numpy()
    pool_cap = CELLS_PER_TYPE * N_REPLICATES
    picks = []
    for lab in np.unique(labels):
        available = np.where(labels == lab)[0]
        picks.append(rng.choice(available, min(pool_cap, len(available)), replace=False))
    pool = adata[np.sort(np.concatenate(picks))].to_memory()

    feats = published_features(organ)
    keep = [g for g in feats if g in set(pool.var_names)]
    return pool[:, keep].copy()


def train_replicates(organ: str, n_replicates: int = N_REPLICATES, seed: int = 0) -> ReplicateSet:
    """Retrain one organ's classifier ``n_replicates`` times on resampled cells."""
    import celltypist

    rng = np.random.default_rng(seed)
    pool = load_pool(organ, rng)
    labels = pool.obs[LABEL_COL].to_numpy()
    uniq = np.unique(labels)
    n_pool = {str(lab): int((labels == lab).sum()) for lab in uniq}

    # celltypist drops non-expressed genes per run, so each replicate returns a
    # slightly different feature set. Scatter every replicate back onto the
    # pool's gene space (a dropped gene carries no weight, hence zero).
    genes = np.asarray(pool.var_names, dtype=object).astype(str)
    gene_index = {g: i for i, g in enumerate(genes)}
    coefs: list[np.ndarray] = []
    label_order: list[str] | None = None

    # Shuffle each label's pool once, then hand replicate b the b-th disjoint
    # fold. Labels without enough cells for N_REPLICATES folds keep all of
    # their cells in every replicate.
    fold_rng = np.random.default_rng(seed + 500)
    folds: dict[str, list[np.ndarray]] = {}
    eligible: dict[str, bool] = {}
    for lab in uniq:
        available = np.where(labels == lab)[0]
        has_folds = len(available) >= CELLS_PER_TYPE * n_replicates
        eligible[str(lab)] = bool(has_folds)
        if has_folds:
            shuffled = fold_rng.permutation(available)
            folds[str(lab)] = [
                shuffled[b * CELLS_PER_TYPE : (b + 1) * CELLS_PER_TYPE]
                for b in range(n_replicates)
            ]
        else:
            folds[str(lab)] = [available] * n_replicates

    for replicate in range(n_replicates):
        picks = [folds[str(lab)][replicate] for lab in uniq]
        subset = pool[np.sort(np.concatenate(picks))].copy()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = celltypist.train(
                subset,
                labels=LABEL_COL,
                feature_selection=False,
                check_expression=False,
                n_jobs=-1,
            )
        replicate_labels = [str(c) for c in model.classifier.classes_]
        if label_order is None:
            label_order = replicate_labels
        elif replicate_labels != label_order:
            raise RuntimeError(
                f"{organ}: replicate {replicate} trained on a different label set"
            )

        aligned = np.zeros((len(label_order), len(genes)), dtype=np.float64)
        cols = np.array([gene_index[g] for g in np.asarray(model.features).astype(str)])
        aligned[:, cols] = np.asarray(model.classifier.coef_, dtype=np.float64)
        coefs.append(aligned)

    assert label_order is not None
    return ReplicateSet(
        organ=organ,
        genes=genes,
        labels=label_order,
        coefs=np.stack(coefs),
        n_pool=n_pool,
        eligible=eligible,
    )


def replicate_stability(replicates: ReplicateSet) -> pd.DataFrame:
    """Mean pairwise cosine between replicate coefficient vectors, per cell type."""
    import itertools

    n_rep = replicates.coefs.shape[0]
    rows = []
    for i, label in enumerate(replicates.labels):
        vectors = replicates.coefs[:, i, :]
        norms = np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12, None)
        unit = vectors / norms
        cosines = [float(unit[a] @ unit[b]) for a, b in itertools.combinations(range(n_rep), 2)]
        rows.append(
            {
                "organ": replicates.organ,
                "curated_label": label,
                "stability": float(np.mean(cosines)),
                "stability_min": float(np.min(cosines)),
                "n_pool_cells": replicates.n_pool.get(label, 0),
                "eligible": replicates.eligible.get(label, False),
            }
        )
    return pd.DataFrame(rows)


def published_agreement(replicates: ReplicateSet) -> pd.DataFrame:
    """Cosine between the mean replicate vector and the published coefficients.

    Confirms that the capped-subsample retrains recover the released model, so
    stability measured here transfers to the published weights.
    """
    with model_file(replicates.organ).open("rb") as handle:
        payload = pickle.load(handle)  # noqa: S301 - first-party CellTypist release
    clf = payload["Model"]
    pub_genes = np.asarray(clf.features, dtype=object).astype(str)
    pub_index = {g: i for i, g in enumerate(pub_genes)}
    pub_labels = {str(c): i for i, c in enumerate(clf.classes_)}

    rep_genes = replicates.genes.astype(str)
    shared = np.intersect1d(pub_genes, rep_genes)
    pub_slice = np.array([pub_index[g] for g in shared])
    rep_index = {g: i for i, g in enumerate(rep_genes)}
    rep_slice = np.array([rep_index[g] for g in shared])

    mean_coef = replicates.coefs.mean(axis=0)
    rows = []
    for i, label in enumerate(replicates.labels):
        if label not in pub_labels:
            continue
        u = clf.coef_[pub_labels[label]][pub_slice]
        v = mean_coef[i][rep_slice]
        denom = np.linalg.norm(u) * np.linalg.norm(v)
        rows.append(
            {
                "organ": replicates.organ,
                "curated_label": label,
                "cosine_vs_published": float(u @ v / denom) if denom else 0.0,
            }
        )
    return pd.DataFrame(rows)
