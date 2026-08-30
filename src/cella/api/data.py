"""In-memory access to the emitted pipeline artifacts.

Loads the small Parquet artifacts from ``settings.processed_dir`` once and caches
them. This is the interim data layer; a later step swaps it for PostgreSQL
without changing the router signatures. See docs/CONCEPT.md §6.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from cella.core.config import settings


class ArtifactsNotBuilt(RuntimeError):
    """Raised when the processed artifacts are missing (run `cella build`)."""


def _read(name: str) -> pd.DataFrame:
    path = settings.processed_dir / name
    if not path.exists():
        raise ArtifactsNotBuilt(f"missing {path}; run `cella build` first")
    return pd.read_parquet(path)


@lru_cache(maxsize=1)
def registry() -> pd.DataFrame:
    """Canonical cross-organ cell types (CELL_TYPE), keyed by cl_id."""
    return _read("registry.parquet")


@lru_cache(maxsize=1)
def cell_type_organ() -> pd.DataFrame:
    """Per (organ, curated type) counts + cl_id (CELL_TYPE_ORGAN)."""
    return _read("cell_type_organ.parquet")


@lru_cache(maxsize=1)
def markers() -> pd.DataFrame:
    """Top-N discriminative genes per (organ, cell type) with direction + rank."""
    return _read("markers.parquet")


@lru_cache(maxsize=1)
def organs() -> pd.DataFrame:
    """Per-organ meta summary for the Organ Browser."""
    return _read("organs.parquet")


@lru_cache(maxsize=1)
def graph_nodes() -> pd.DataFrame:
    """Relationship-graph nodes (harmonized cell types with layout coords)."""
    return _read("graph_nodes.parquet")


@lru_cache(maxsize=1)
def graph_edges() -> pd.DataFrame:
    """Relationship-graph edges (undirected cell-type similarity)."""
    return _read("graph_edges.parquet")


@lru_cache(maxsize=16)
def weights(slug: str) -> pd.DataFrame:
    """Full classifier weight matrix (curated cell type x gene) for one organ."""
    path = settings.processed_dir / "weights" / f"{slug}.parquet"
    if not path.exists():
        raise ArtifactsNotBuilt(f"missing {path}; run `cella build` first")
    return pd.read_parquet(path)


@lru_cache(maxsize=16)
def obs(slug: str) -> pd.DataFrame:
    """Cached cell metadata for one organ (by underscore slug)."""
    path = settings.raw_dir / "obs" / f"{slug}.parquet"
    if not path.exists():
        raise ArtifactsNotBuilt(f"missing {path}; run `cella acquire obs` first")
    return pd.read_parquet(path)


def expression(slug: str, kind: str) -> pd.DataFrame | None:
    """Pseudobulk matrix (kind='mean' or 'pct') for one organ, or None if not derived."""
    path = settings.processed_dir / "expression" / f"{slug}__{kind}.parquet"
    return pd.read_parquet(path) if path.exists() else None


@lru_cache(maxsize=16)
def embedding(slug: str) -> pd.DataFrame | None:
    """Downsampled UMAP scatter (x, y, cell_type) for one organ, or None."""
    path = settings.processed_dir / "embedding" / f"{slug}.parquet"
    return pd.read_parquet(path) if path.exists() else None


@lru_cache(maxsize=16)
def tf_activity(slug: str) -> pd.DataFrame | None:
    """TF-activity matrix (cell_type x TF) for one organ, or None if not derived."""
    path = settings.processed_dir / "tf" / f"{slug}.parquet"
    return pd.read_parquet(path) if path.exists() else None


@lru_cache(maxsize=128)
def gsea(slug: str, collection: str = "hallmark") -> pd.DataFrame | None:
    """Gene-set-activity matrix (cell_type x set) for a collection, or None."""
    path = settings.processed_dir / "gsea" / f"{slug}__{collection}.parquet"
    return pd.read_parquet(path) if path.exists() else None


@lru_cache(maxsize=16)
def cci(slug: str) -> pd.DataFrame | None:
    """Top ligand-receptor interactions (source, target, ligand, receptor, score)."""
    path = settings.processed_dir / "cci" / f"{slug}.parquet"
    return pd.read_parquet(path) if path.exists() else None
