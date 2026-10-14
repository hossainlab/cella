"""P1 - Emit artifacts.

Write the query-ready artifacts the online app serves, into
``settings.processed_dir`` as Parquet:

    registry.parquet          canonical cross-organ cell types (CELL_TYPE, ~145)
    cl_relatives.parquet      close ontology relatives among the registry terms
    cell_type_organ.parquet   per (organ, curated type) counts + CL id (~399)
    weights/<Organ>.parquet    full classifier.coef_ (cell_type x gene) per organ
    markers.parquet            top-N discriminative genes per (organ, cell type),
                               gated on expression prevalence (see select_markers)

The markers table is the direct input to the Discriminative Marker Atlas and the
Fingerprint Explorer; the full weight matrices back consensus/fingerprint math.
A future step loads these into PostgreSQL. See docs/CONCEPT.md §5.6-5.7, §6.
"""

from __future__ import annotations

import pandas as pd

from cella.core.config import ORGANS, settings
from cella.pipeline.extract import extract_weights, load_obs
from cella.pipeline.harmonize import build_long_metadata, build_registry
from cella.pipeline.ontology import close_relatives

# obs columns summarized for the Organ Browser meta panel.
_META_COLS = {
    "datasets": "Dataset",
    "donors": "donor_id",
    "assays": "assay",
    "diseases": "disease",
    "dev_stages": "development_stage",
}


def emit_organ_summary() -> pd.DataFrame:
    """Per-organ meta (cell counts, datasets, donors, assays) for the Organ Browser."""
    out = settings.processed_dir
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for organ in ORGANS:
        obs = load_obs(organ)
        row: dict[str, object] = {"organ": organ, "n_cells": len(obs)}
        row["n_cell_types"] = obs["Curated_annotation"].nunique()
        for key, col in _META_COLS.items():
            row[f"n_{key}"] = obs[col].nunique() if col in obs.columns else 0
        # store the actual dataset/assay lists (pipe-joined) for the detail view
        for key, col in (("datasets_list", "Dataset"), ("assays_list", "assay")):
            row[key] = (
                " | ".join(sorted(map(str, obs[col].dropna().unique())))
                if col in obs.columns
                else ""
            )
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_parquet(out / "organs.parquet")
    return df


def emit_metadata() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Emit the registry (CELL_TYPE) and cell_type_organ tables."""
    out = settings.processed_dir
    out.mkdir(parents=True, exist_ok=True)
    long = build_long_metadata()
    registry = build_registry(long)
    # list columns -> JSON-ish strings so parquet stays simple/portable.
    reg_out = registry.assign(
        organs=registry["organs"].map(lambda xs: ", ".join(xs)),
        aliases=registry["aliases"].map(lambda xs: " | ".join(xs)),
    )
    reg_out.to_parquet(out / "registry.parquet")
    long.to_parquet(out / "cell_type_organ.parquet")
    relatives = close_relatives(sorted(registry["cl_id"].dropna().unique()))
    pd.DataFrame(
        [(cid, rel) for cid, rels in sorted(relatives.items()) for rel in sorted(rels)],
        columns=["cl_id", "relative"],
    ).to_parquet(out / "cl_relatives.parquet")
    return registry, long


def select_markers(
    coef: pd.Series,
    pct_in: pd.Series,
    pct_out_max: pd.Series,
    top_n: int = 25,
    min_pct: float = 0.1,
) -> dict[str, pd.Series]:
    """Top-N positive and negative markers, gated on expression prevalence.

    CellTypist scales each gene before fitting, so a gene detected in almost no
    cells gets a large scaled value wherever it does appear and can earn a large
    coefficient for a rare class (e.g. FOXP3 in lung goblet cells). Such genes
    help the classifier on a handful of training cells but are not markers.

    A positive marker must be expressed in at least ``min_pct`` of the cell
    type's own cells. A negative marker argues *against* the cell type, which is
    only informative if some other cell type in the organ expresses it, so it
    must reach ``min_pct`` in at least one other cell type.
    """
    pct_in = pct_in.reindex(coef.index)
    pct_out_max = pct_out_max.reindex(coef.index)
    positive = coef[pct_in >= min_pct].sort_values(ascending=False).head(top_n)
    negative = coef[pct_out_max >= min_pct].sort_values().head(top_n)
    return {"positive": positive, "negative": negative}


def _load_pct(organ: str) -> pd.DataFrame:
    """Fraction of cells expressing each gene, per curated label (from ``cella derive``)."""
    path = settings.processed_dir / "expression" / f"{organ.replace(' ', '_')}__pct.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run `cella derive` before `cella build`")
    return pd.read_parquet(path)


def emit_weights_and_markers(top_n: int = 25, min_pct: float = 0.1) -> pd.DataFrame:
    """Emit per-organ weight matrices and a combined top-N markers table."""
    out = settings.processed_dir
    (out / "weights").mkdir(parents=True, exist_ok=True)
    long = build_long_metadata()
    # curated label -> cl_id per organ, for annotating marker rows.
    key = long.set_index(["organ", "curated_label"])["cl_id"].to_dict()

    marker_frames: list[pd.DataFrame] = []
    for organ in ORGANS:
        w = extract_weights(organ)
        w.matrix.to_parquet(out / "weights" / f"{organ.replace(' ', '_')}.parquet")
        pct = _load_pct(organ).reindex(columns=w.matrix.columns)
        for cell_type, row in w.matrix.iterrows():
            pct_in = pct.loc[cell_type]
            pct_out_max = pct.drop(index=cell_type).max()
            selected = select_markers(row, pct_in, pct_out_max, top_n=top_n, min_pct=min_pct)
            for direction, series in selected.items():
                frame = series.rename_axis("gene").reset_index(name="coef")
                frame.insert(0, "organ", organ)
                frame.insert(1, "cell_type", cell_type)
                frame.insert(2, "cl_id", key.get((organ, cell_type)))
                frame["direction"] = direction
                frame["rank"] = range(1, len(frame) + 1)
                frame["pct_in"] = pct_in.reindex(series.index).to_numpy(dtype="float32")
                frame["pct_out_max"] = pct_out_max.reindex(series.index).to_numpy(dtype="float32")
                marker_frames.append(frame)

    markers = pd.concat(marker_frames, ignore_index=True)
    markers.to_parquet(out / "markers.parquet")
    return markers


def emit_all(top_n: int = 25, min_pct: float = 0.1) -> None:
    """Emit every artifact. Idempotent; overwrites in place."""
    registry, long = emit_metadata()
    markers = emit_weights_and_markers(top_n=top_n, min_pct=min_pct)
    print(
        f"emitted: registry={len(registry)} nodes, "
        f"cell_type_organ={len(long)} rows, markers={len(markers)} rows "
        f"-> {settings.processed_dir}"
    )
