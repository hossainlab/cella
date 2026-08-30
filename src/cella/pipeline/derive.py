"""Expression derivation for the Organ Browser (stage 1: pseudobulk).

Turns each downloaded .h5ad atlas into a small, query-ready expression summary:
mean expression and fraction of cells expressing, per (cell type x gene). This
is the standard dot-plot matrix and the foundation for differential expression.

Memory-safe: reads X in row chunks from a backed AnnData, so a 3 GB atlas never
loads fully into RAM. Output per organ (~cell_types x genes, a few MB):

    data/processed/expression/<Organ>__mean.parquet   mean expression
    data/processed/expression/<Organ>__pct.parquet    fraction expressing (0-1)

See docs/CONCEPT.md (Organ Browser extension).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

from cella.core.config import ORGANS, settings
from cella.pipeline.acquire import atlas_path
from cella.pipeline.extract import MODEL_LABEL_COL

CHUNK = 20_000  # cells per streamed block


def _expression_dir() -> Path:
    d = settings.processed_dir / "expression"
    d.mkdir(parents=True, exist_ok=True)
    return d


def compute_pseudobulk(
    organ: str, label_col: str = MODEL_LABEL_COL
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean expression and fraction-expressing per (cell type x gene) for one organ.

    Streams X in chunks; aggregates with a group-indicator sparse matmul.
    """
    path = atlas_path(organ)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `cella acquire atlases` first")

    adata = ad.read_h5ad(path, backed="r")
    labels = pd.Categorical(adata.obs[label_col].astype(str))
    groups = list(labels.categories)
    n_groups, n_genes = len(groups), adata.n_vars

    sums = np.zeros((n_groups, n_genes), dtype=np.float64)
    nnz = np.zeros((n_groups, n_genes), dtype=np.float64)
    counts = np.zeros(n_groups, dtype=np.float64)

    for start in range(0, adata.n_obs, CHUNK):
        stop = min(start + CHUNK, adata.n_obs)
        codes = labels.codes[start:stop]
        # group-indicator: (n_groups x chunk), one-hot of each cell's group
        g = sp.csr_matrix(
            (np.ones(stop - start), (codes, np.arange(stop - start))),
            shape=(n_groups, stop - start),
        )
        x = adata.X[start:stop]
        xs = sp.csr_matrix(x) if not sp.issparse(x) else x
        sums += (g @ xs).toarray()
        nnz += (g @ (xs > 0).astype(np.float64)).toarray()
        np.add.at(counts, codes, 1)

    counts_safe = np.where(counts == 0, 1, counts)[:, None]
    mean = pd.DataFrame(sums / counts_safe, index=groups, columns=adata.var_names)
    pct = pd.DataFrame(nnz / counts_safe, index=groups, columns=adata.var_names)
    mean.index.name = pct.index.name = "cell_type"
    return mean, pct


def derive_expression(organs: tuple[str, ...] = ORGANS) -> None:
    """Compute and write pseudobulk artifacts for the given organs (skips existing)."""
    out = _expression_dir()
    for organ in organs:
        safe = organ.replace(" ", "_")
        if (out / f"{safe}__mean.parquet").exists():
            print(f"pseudobulk {organ}: exists, skipping")
            continue
        mean, pct = compute_pseudobulk(organ)
        mean.to_parquet(out / f"{safe}__mean.parquet")
        pct.to_parquet(out / f"{safe}__pct.parquet")
        print(f"pseudobulk {organ}: {mean.shape[0]} cell types x {mean.shape[1]} genes")


def compute_embedding(
    organ: str, max_points: int = 25_000, label_col: str = MODEL_LABEL_COL
) -> pd.DataFrame:
    """Downsampled UMAP scatter (x, y, cell_type) for one organ's Overview plot."""
    path = atlas_path(organ)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; put atlases in {settings.atlas_dir}")
    adata = ad.read_h5ad(path, backed="r")
    xy = np.asarray(adata.obsm["X_umap"])
    ct = adata.obs[label_col].astype(str).to_numpy()
    n = xy.shape[0]
    if n > max_points:
        rng = np.random.default_rng(0)
        idx = np.sort(rng.choice(n, max_points, replace=False))
        xy, ct = xy[idx], ct[idx]
    return pd.DataFrame(
        {"x": xy[:, 0].round(3), "y": xy[:, 1].round(3), "cell_type": ct}
    )


def derive_embeddings(organs: tuple[str, ...] = ORGANS) -> None:
    """Write downsampled UMAP coordinates per organ for the scatter plot (skips existing)."""
    out = settings.processed_dir / "embedding"
    out.mkdir(parents=True, exist_ok=True)
    for organ in organs:
        dest = out / f"{organ.replace(' ', '_')}.parquet"
        if dest.exists():
            print(f"embedding {organ}: exists, skipping")
            continue
        df = compute_embedding(organ)
        df.to_parquet(dest)
        print(f"embedding {organ}: {len(df):,} points")


# --------------------------------------------------------------------------- #
# TF activity (decoupler ULM over CollecTRI regulons, on the pseudobulk means)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def _collectri() -> pd.DataFrame:
    import decoupler as dc

    return dc.op.collectri(organism="human")


def _mean_symbols(organ: str) -> pd.DataFrame:
    """Pseudobulk mean matrix with columns collapsed to gene symbols."""
    safe = organ.replace(" ", "_")
    mean = pd.read_parquet(settings.processed_dir / "expression" / f"{safe}__mean.parquet")
    mean.columns = [str(c).split("_ENSG")[0] for c in mean.columns]
    return mean.loc[:, ~mean.columns.duplicated()]


def compute_tf_activity(organ: str) -> pd.DataFrame:
    """TF activity per (cell type x TF) via ULM on the mean-expression matrix."""
    import anndata as ad
    import decoupler as dc

    adata = ad.AnnData(_mean_symbols(organ))
    dc.mt.ulm(adata, _collectri())
    return adata.obsm["score_ulm"]


def derive_tf(organs: tuple[str, ...] = ORGANS) -> None:
    """Write TF-activity matrices per organ (needs pseudobulk; skips existing)."""
    out = settings.processed_dir / "tf"
    out.mkdir(parents=True, exist_ok=True)
    for organ in organs:
        dest = out / f"{organ.replace(' ', '_')}.parquet"
        if dest.exists():
            print(f"tf {organ}: exists, skipping")
            continue
        acts = compute_tf_activity(organ)
        acts.to_parquet(dest)
        print(f"tf {organ}: {acts.shape[0]} cell types x {acts.shape[1]} TFs")


# --------------------------------------------------------------------------- #
# Pathway enrichment (decoupler ULM over MSigDB Hallmark gene sets)
# --------------------------------------------------------------------------- #

# MSigDB gene-set collections offered in the GSEA panel (key -> MSigDB category).
GSEA_COLLECTIONS: dict[str, str] = {
    "hallmark": "h.all",
    "kegg": "c2.cp.kegg_medicus",
    "go_bp": "c5.go.bp",
    "oncogenic": "c6.all",
    "immunologic": "c7.immunesigdb",
    "tft": "c3.tft.gtrd",
}
_MSIGDB_VER = "2023.2.Hs"


@lru_cache(maxsize=len(GSEA_COLLECTIONS))
def _gene_set_net(collection: str) -> pd.DataFrame:
    """MSigDB collection as a decoupler net (source=gene set, target=gene)."""
    import gseapy as gp

    gmt = gp.Msigdb().get_gmt(category=GSEA_COLLECTIONS[collection], dbver=_MSIGDB_VER)
    return pd.DataFrame(
        [(gs, g) for gs, genes in gmt.items() for g in genes],
        columns=["source", "target"],
    )


def compute_gsea(organ: str, collection: str = "hallmark") -> pd.DataFrame:
    """Gene-set activity per (cell type x set) via ULM on mean expression."""
    import anndata as ad
    import decoupler as dc

    adata = ad.AnnData(_mean_symbols(organ))
    dc.mt.ulm(adata, _gene_set_net(collection))
    return adata.obsm["score_ulm"]


def derive_gsea(
    organs: tuple[str, ...] = ORGANS,
    collections: tuple[str, ...] = tuple(GSEA_COLLECTIONS),
) -> None:
    """Write gene-set-activity matrices per organ and collection (skips existing)."""
    out = settings.processed_dir / "gsea"
    out.mkdir(parents=True, exist_ok=True)
    for collection in collections:
        for organ in organs:
            dest = out / f"{organ.replace(' ', '_')}__{collection}.parquet"
            if dest.exists():
                print(f"gsea {organ}/{collection}: exists, skipping")
                continue
            acts = compute_gsea(organ, collection)
            acts.to_parquet(dest)
            print(f"gsea {organ}/{collection}: {acts.shape[0]} x {acts.shape[1]} sets")


# --------------------------------------------------------------------------- #
# Cell-cell interaction (ligand-receptor, CellPhoneDB-style on the pseudobulk)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def _lr_resource() -> pd.DataFrame:
    import liana as li

    return li.rs.select_resource("consensus")


def _pct_symbols(organ: str) -> pd.DataFrame:
    safe = organ.replace(" ", "_")
    pct = pd.read_parquet(settings.processed_dir / "expression" / f"{safe}__pct.parquet")
    pct.columns = [str(c).split("_ENSG")[0] for c in pct.columns]
    return pct.loc[:, ~pct.columns.duplicated()]


def compute_cci(
    organ: str, min_frac: float = 0.1, top_per_pair: int = 3, keep: int = 1500
) -> pd.DataFrame:
    """Score ligand->receptor interactions between cell types on mean expression.

    score = mean(ligand in source) * mean(receptor in target), gated so a fraction
    >= ``min_frac`` of cells express every subunit. Complexes use the min subunit.
    """
    mean = _mean_symbols(organ)
    pct = _pct_symbols(organ)
    genes = set(mean.columns)
    cts = list(mean.index)

    def subunit_min(mat: pd.DataFrame, complex_str: str) -> np.ndarray | None:
        subs = complex_str.split("_")
        if not all(s in genes for s in subs):
            return None
        return mat[subs].min(axis=1).to_numpy()

    rows: list[tuple[str, str, str, str, float]] = []
    for lig, rec in _lr_resource().itertuples(index=False):
        lm, rm = subunit_min(mean, lig), subunit_min(mean, rec)
        if lm is None or rm is None:
            continue
        lf, rf = subunit_min(pct, lig), subunit_min(pct, rec)
        score = np.outer(lm, rm)
        score = np.where(np.outer(lf >= min_frac, rf >= min_frac), score, 0.0)
        flat = score.ravel()
        for idx in np.argsort(flat)[::-1][:top_per_pair]:
            if flat[idx] <= 0:
                break
            si, ti = divmod(int(idx), score.shape[1])
            rows.append((cts[si], cts[ti], lig, rec, float(flat[idx])))

    df = pd.DataFrame(rows, columns=["source", "target", "ligand", "receptor", "score"])
    return df.sort_values("score", ascending=False).head(keep).reset_index(drop=True)


def derive_cci(organs: tuple[str, ...] = ORGANS) -> None:
    """Write top ligand-receptor interactions per organ (needs pseudobulk; skips existing)."""
    out = settings.processed_dir / "cci"
    out.mkdir(parents=True, exist_ok=True)
    for organ in organs:
        dest = out / f"{organ.replace(' ', '_')}.parquet"
        if dest.exists():
            print(f"cci {organ}: exists, skipping")
            continue
        df = compute_cci(organ)
        df.to_parquet(dest)
        print(f"cci {organ}: {len(df)} interactions")
