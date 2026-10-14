"""Are classifier-coefficient markers better marker panels than DE markers?

Cella ranks markers by CellTypist logistic-regression coefficients rather than
by differential expression. This module tests whether that choice produces
better small marker panels, on cells from a dataset neither method has seen.

Protocol (per organ, leave one dataset out)
-------------------------------------------
* **Split.** Each source dataset of the organ is held out in turn. Training
  cells come from the other datasets, test cells from the held-out one, capped
  per label (``TRAIN_CAP`` / ``TEST_CAP``) so abundant types do not dominate.
  Labels with fewer than ``MIN_TRAIN`` training cells are left out of training;
  a label is tested only if it also has ``MIN_TEST`` cells in the held-out
  dataset.
* **Genes.** Everything is restricted to the released model's feature set, so
  the methods differ only in how they rank genes, not in which genes they see.
* **Marker rankings** (top-k positive markers per label, all from training
  cells only):

  - ``coef_raw``   - retrain CellTypist (``celltypist.train`` defaults) and rank
    by coefficient, as the raw released weights would be read.
  - ``coef_gated`` - the same coefficients after the prevalence gate used for
    the marker table (expressed in >= ``MIN_PCT`` of the label's cells).
  - ``de_wilcoxon`` - scanpy one-vs-rest Wilcoxon, ranked by score.
  - ``de_logfc``   - one-vs-rest log fold change with the same prevalence gate,
    a common quick heuristic.

* **Panel scoring.** For each k, the union of every label's top-k markers is
  the panel. Two readouts on the held-out cells:

  - ``lr``     - a fresh multinomial logistic regression trained on the panel
    genes (identical model for every method), macro-F1 on test.
  - ``marker`` - classifier-free annotation: each cell gets the label whose own
    k markers have the highest mean z-score (z from training cells). This is
    how marker lists are used in practice, without a model.

The two readouts answer different questions: ``lr`` asks whether the panel
carries the information, ``marker`` asks whether each label's own list is
usable on its own.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cella.analysis.stability import LABEL_COL, counts_file, published_features

DATASET_COL = "Dataset"
TRAIN_CAP = 500
TEST_CAP = 300
MIN_TRAIN = 50
MIN_TEST = 20
MIN_PCT = 0.1
K_VALUES = (3, 5, 10, 20)
METHODS = ("coef_raw", "coef_gated", "de_wilcoxon", "de_logfc")
OUT_DIR = Path("data/processed/benchmark_panels")


@dataclass
class Split:
    organ: str
    held_out: str
    train: object  # AnnData, published features only, in memory
    test: object


def _cap(labels: np.ndarray, idx: np.ndarray, cap: int, rng: np.random.Generator) -> np.ndarray:
    picks = []
    for lab in np.unique(labels[idx]):
        avail = idx[labels[idx] == lab]
        picks.append(rng.choice(avail, min(cap, len(avail)), replace=False))
    return np.sort(np.concatenate(picks))


def make_splits(organ: str, seed: int = 0):
    """Yield one leave-one-dataset-out split per source dataset of the organ."""
    import anndata as ad

    adata = ad.read_h5ad(counts_file(organ), backed="r")
    labels = adata.obs[LABEL_COL].astype(str).to_numpy()
    datasets = adata.obs[DATASET_COL].astype(str).to_numpy()
    feats = published_features(organ)
    keep = [g for g in feats if g in set(adata.var_names)]
    rng = np.random.default_rng(seed)

    for held_out in sorted(set(datasets)):
        tr_all = np.where(datasets != held_out)[0]
        te_all = np.where(datasets == held_out)[0]
        tr_counts = pd.Series(labels[tr_all]).value_counts()
        te_counts = pd.Series(labels[te_all]).value_counts()
        testable = set(te_counts[te_counts >= MIN_TEST].index) & set(
            tr_counts[tr_counts >= MIN_TRAIN].index
        )
        if len(testable) < 3:
            continue
        # Train only on labels with enough cells for every method (Wilcoxon needs >1).
        tr_ok = tr_all[np.isin(labels[tr_all], tr_counts[tr_counts >= MIN_TRAIN].index)]
        tr = _cap(labels, tr_ok, TRAIN_CAP, rng)
        te = te_all[np.isin(labels[te_all], list(testable))]
        te = _cap(labels, te, TEST_CAP, rng)
        rows = np.concatenate([tr, te])
        order = np.argsort(rows)
        block = adata[rows[order]].to_memory()[:, keep]
        is_train = np.isin(rows[order], tr)
        yield Split(organ, held_out, block[is_train].copy(), block[~is_train].copy())


# --------------------------------------------------------------------------- rankings


def _dense(x) -> np.ndarray:
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)


def _pct_by_label(adata) -> pd.DataFrame:
    labels = adata.obs[LABEL_COL].astype(str).to_numpy()
    x = adata.X
    rows = {}
    for lab in np.unique(labels):
        sub = x[labels == lab]
        rows[lab] = np.asarray((sub > 0).mean(axis=0)).ravel()
    return pd.DataFrame(rows, index=adata.var_names).T


def rank_markers(train, k_max: int = max(K_VALUES)) -> dict[str, dict[str, list[str]]]:
    """method -> label -> top-``k_max`` positive marker genes, from training cells only."""
    import celltypist
    import scanpy as sc

    labels = train.obs[LABEL_COL].astype(str)
    pct = _pct_by_label(train)
    out: dict[str, dict[str, list[str]]] = {m: {} for m in METHODS}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = celltypist.train(
            train, labels=LABEL_COL, feature_selection=False, check_expression=False, n_jobs=-1
        )
    coef = pd.DataFrame(
        model.classifier.coef_,
        index=[str(c) for c in model.classifier.classes_],
        columns=np.asarray(model.features).astype(str),
    )
    for lab in coef.index:
        row = coef.loc[lab]
        out["coef_raw"][lab] = list(row.nlargest(k_max).index)
        ok = pct.loc[lab].reindex(row.index) >= MIN_PCT
        out["coef_gated"][lab] = list(row[ok].nlargest(k_max).index)

    ad_de = train.copy()
    ad_de.raw = None  # the atlases carry .raw (all genes); rank the shared feature set only
    ad_de.obs[LABEL_COL] = labels.astype("category")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sc.tl.rank_genes_groups(
            ad_de, LABEL_COL, method="wilcoxon", n_genes=ad_de.n_vars, use_raw=False
        )
    res = ad_de.uns["rank_genes_groups"]
    for lab in res["names"].dtype.names:
        out["de_wilcoxon"][lab] = [str(g) for g in res["names"][lab][:k_max]]

    x = train.X
    for lab in np.unique(labels):
        mask = (labels == lab).to_numpy()
        m_in = np.asarray(x[mask].mean(axis=0)).ravel()
        m_out = np.asarray(x[~mask].mean(axis=0)).ravel()
        lfc = pd.Series(m_in - m_out, index=train.var_names)  # log1p space: a log ratio
        ok = pct.loc[lab].reindex(lfc.index) >= MIN_PCT
        out["de_logfc"][lab] = list(lfc[ok].nlargest(k_max).index)
    return out


# --------------------------------------------------------------------------- scoring


def _macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    from sklearn.metrics import f1_score

    return float(f1_score(y_true, y_pred, average="macro"))


def score_panel(split: Split, markers: dict[str, list[str]], k: int) -> dict[str, float]:
    """``lr`` and ``marker`` macro-F1 on held-out cells for one method's top-k panel."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    test_labels = sorted(set(split.test.obs[LABEL_COL].astype(str)))
    per_label = {lab: markers.get(lab, [])[:k] for lab in markers}
    panel = sorted({g for genes in per_label.values() for g in genes})
    y_tr = split.train.obs[LABEL_COL].astype(str).to_numpy()
    y_te = split.test.obs[LABEL_COL].astype(str).to_numpy()

    x_tr = _dense(split.train[:, panel].X)
    x_te = _dense(split.test[:, panel].X)
    scaler = StandardScaler().fit(x_tr)
    z_tr, z_te = scaler.transform(x_tr), scaler.transform(x_te)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf = LogisticRegression(max_iter=1000, C=1.0).fit(z_tr, y_tr)
    lr_f1 = _macro_f1(y_te, clf.predict(z_te))

    # Classifier-free: argmax over labels of the mean z of that label's markers.
    col = {g: i for i, g in enumerate(panel)}
    labs = [lab for lab in per_label if per_label[lab]]
    scores = np.column_stack(
        [z_te[:, [col[g] for g in per_label[lab]]].mean(axis=1) for lab in labs]
    )
    marker_pred = np.asarray(labs, dtype=object)[scores.argmax(axis=1)]
    marker_f1 = _macro_f1(y_te, marker_pred)

    return {
        "panel_size": len(panel),
        "n_test_labels": len(test_labels),
        "n_test_cells": len(y_te),
        "lr_f1": lr_f1,
        "marker_f1": marker_f1,
    }


def run_organ(organ: str, seed: int = 0) -> pd.DataFrame:
    """All splits x methods x k for one organ; also stores the marker lists."""
    rows = []
    marker_rows = []
    for split in make_splits(organ, seed=seed):
        markers = rank_markers(split.train)
        for method, per_label in markers.items():
            for lab, genes in per_label.items():
                marker_rows.extend(
                    {
                        "organ": organ,
                        "held_out": split.held_out,
                        "method": method,
                        "label": lab,
                        "rank": r + 1,
                        "gene": g,
                    }
                    for r, g in enumerate(genes)
                )
            for k in K_VALUES:
                rows.append(
                    {
                        "organ": organ,
                        "held_out": split.held_out,
                        "method": method,
                        "k": k,
                        **score_panel(split, per_label, k),
                    }
                )
        print(f"  {organ} | held out {split.held_out}: done", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(marker_rows).to_parquet(OUT_DIR / f"{organ.replace(' ', '_')}__markers.parquet")
    return pd.DataFrame(rows)
