"""P1 - Extraction.

Turn the two local inputs (a ``.pkl`` model + a cached ``.obs`` parquet per
organ) into tidy in-memory structures for harmonization and emit:

- ``extract_weights``  : the (cell_type x gene) classifier coefficient matrix,
  the discriminative signal every v1 tool is built on.
- ``extract_metadata`` : per-cell-type counts and label columns from the cached
  ``.obs`` (High/Low granularity, dataset provenance, ontology labels).

See docs/CONCEPT.md §5.2-5.3.
"""

from __future__ import annotations

from dataclasses import dataclass

import celltypist
import pandas as pd

from cella.pipeline.acquire import cache_obs_one, model_path, obs_path
from cella.pipeline.ontology import map_labels


@dataclass(frozen=True)
class OrganWeights:
    """One organ's classifier weights, indexed by cell type x gene."""

    organ: str
    matrix: pd.DataFrame  # rows = cell types, cols = genes, values = coef


def extract_weights(organ: str) -> OrganWeights:
    """Load the organ's .pkl model and return its classifier.coef_ as a DataFrame."""
    model = celltypist.models.Model.load(str(model_path(organ)))
    matrix = pd.DataFrame(
        model.classifier.coef_,
        index=pd.Index(model.cell_types, name="cell_type"),
        columns=pd.Index(model.features, name="gene"),
    )
    return OrganWeights(organ=organ, matrix=matrix)


def load_obs(organ: str) -> pd.DataFrame:
    """Return the cached .obs for an organ, fetching it remotely if not yet cached."""
    path = obs_path(organ)
    if not path.exists():
        cache_obs_one(organ)
    return pd.read_parquet(path)


# The model's cell_types match obs["Curated_annotation"] exactly (49/49 for Lung),
# so that is the join key. obs["cell_type"] is the coarser Cell Ontology label
# (many curated types -> one CL term) and is kept as the harmonization bridge.
MODEL_LABEL_COL = "Curated_annotation"
ONTOLOGY_LABEL_COL = "cell_type"


def extract_metadata(organ: str, label_col: str = MODEL_LABEL_COL) -> pd.DataFrame:
    """Per-cell-type cell counts for one organ, from the cached .obs table.

    Defaults to ``Curated_annotation`` (the model's label space). Where present,
    the Cell Ontology label (``cell_type``) is attached per curated type.
    """
    obs = load_obs(organ)
    if label_col not in obs.columns:
        raise KeyError(f"{label_col!r} not in obs columns: {list(obs.columns)}")
    counts = (
        obs[label_col]
        .value_counts()
        .rename_axis("label")
        .reset_index(name="cell_count")
    )
    # Attach the Cell Ontology label (the most common one per curated type)
    # and its CL id, giving each cell type a stable cross-organ key.
    if ONTOLOGY_LABEL_COL in obs.columns and label_col != ONTOLOGY_LABEL_COL:
        bridge = (
            obs.groupby(label_col, observed=True)[ONTOLOGY_LABEL_COL]
            .agg(lambda s: s.mode().iat[0] if not s.mode().empty else pd.NA)
        )
        counts["ontology_label"] = counts["label"].map(bridge)
        id_map = map_labels([str(x) for x in counts["ontology_label"].dropna().unique()])
        counts["cl_id"] = counts["ontology_label"].map(id_map)
    counts.insert(0, "organ", organ)
    return counts
