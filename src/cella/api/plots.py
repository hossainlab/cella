"""Plotly figure builders for the Organ Browser.

Each function reads a precomputed artifact and returns a Plotly figure as a plain
dict (``fig.to_plotly_json()``) that the frontend renders with plotly.js. Building
server-side keeps the figure definition in Python (scientifically authoritative)
while the browser gets full interactivity (zoom, pan, hover, legend toggle).
"""

from __future__ import annotations

import colorsys
from typing import Any

import numpy as np
import plotly.graph_objects as go

from cella.api import data


def _category_color(i: int) -> str:
    """Match the frontend golden-angle palette so colors are consistent."""
    hue = (i * 137.508) % 360 / 360
    sat = (62 + (i % 3) * 10) / 100
    light = (55 + (i % 2) * 8) / 100
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"


def _fig(fig: go.Figure) -> dict[str, Any]:
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig.to_plotly_json()


def _mean_symbols(slug: str):
    """Pseudobulk mean matrix with columns collapsed to gene symbols."""
    m = data.expression(slug, "mean")
    if m is None:
        return None
    m = m.copy()
    m.columns = [str(c).split("_ENSG")[0] for c in m.columns]
    return m.loc[:, ~m.columns.duplicated()]


def signature_scores(slug: str, genes: list[str]):
    """Per-cell-type module score for a gene signature (mean of z-scored genes)."""
    m = _mean_symbols(slug)
    if m is None:
        return None, [], []
    present = [g for g in genes if g in m.columns]
    missing = [g for g in genes if g not in m.columns]
    if not present:
        return None, present, missing
    sub = m[present]
    z = (sub - sub.mean(axis=0)) / sub.std(axis=0).replace(0, 1.0)
    return z.mean(axis=1), present, missing


def signature_umap_figure(slug: str, genes: list[str]) -> dict[str, Any] | None:
    """UMAP colored by a signature's module score (Single-Cell Signature Explorer style)."""
    score, present, _ = signature_scores(slug, genes)
    if score is None:
        return None
    emb = data.embedding(slug)
    if emb is None:
        return None
    cell_scores = emb["cell_type"].map(score).astype(float)
    lim = float(np.abs(cell_scores).max()) or 1.0
    fig = go.Figure(
        go.Scattergl(
            x=emb["x"].tolist(),
            y=emb["y"].tolist(),
            mode="markers",
            marker=dict(
                size=3,
                color=cell_scores.tolist(),
                colorscale="RdBu_r",
                cmid=0,
                cmin=-lim,
                cmax=lim,
                colorbar=dict(title="score", thickness=12),
            ),
            text=emb["cell_type"].tolist(),
            hovertemplate="%{text}<br>score %{marker.color:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{slug.replace('_', ' ')} — signature ({len(present)} genes)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x"),
        height=560,
    )
    return _fig(fig)


def gene_umap_figure(slug: str, gene: str) -> dict[str, Any] | None:
    """UMAP colored by a single gene's mean expression per cell type (feature plot)."""
    m = _mean_symbols(slug)
    if m is None:
        return None
    matches = [c for c in m.columns if c.upper() == gene.upper()]
    if not matches:
        return None
    per_ct = m[matches[0]]
    emb = data.embedding(slug)
    if emb is None:
        return None
    vals = emb["cell_type"].map(per_ct).astype(float)
    fig = go.Figure(
        go.Scattergl(
            x=emb["x"].tolist(),
            y=emb["y"].tolist(),
            mode="markers",
            marker=dict(
                size=3,
                color=vals.tolist(),
                colorscale="Viridis",
                colorbar=dict(title="mean<br>expr", thickness=12),
            ),
            text=emb["cell_type"].tolist(),
            hovertemplate="%{text}<br>expr %{marker.color:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{slug.replace('_', ' ')} — {gene.upper()} expression",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x"),
        height=520,
    )
    return _fig(fig)


def umap_figure(slug: str) -> dict[str, Any] | None:
    """Interactive UMAP scatter, one trace per cell type (legend toggles it)."""
    df = data.embedding(slug)
    if df is None:
        return None
    cats = list(df["cell_type"].astype("category").cat.categories)
    fig = go.Figure()
    for i, ct in enumerate(cats):
        sub = df[df["cell_type"] == ct]
        fig.add_trace(
            go.Scattergl(
                x=sub["x"],
                y=sub["y"],
                mode="markers",
                name=ct,
                marker=dict(size=3, color=_category_color(i)),
                hovertemplate=f"{ct}<extra></extra>",
            )
        )
    fig.update_layout(
        title=f"{slug.replace('_', ' ')} — {len(df):,} cells (UMAP)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x"),
        legend=dict(itemsizing="constant", font=dict(size=10)),
        height=560,
    )
    return _fig(fig)


def _specificity_heatmap(
    mat, title: str, top_per_ct: int | None, colorscale: str, max_cols: int | None = None
) -> dict[str, Any]:
    """Heatmap of cell type x feature, values centered (specificity)."""
    spec = mat.sub(mat.mean(axis=0), axis=1)
    if top_per_ct is not None:
        keep: list[str] = []
        for ct in spec.index:
            keep += list(spec.loc[ct].sort_values(ascending=False).head(top_per_ct).index)
        cols = list(dict.fromkeys(keep))
        spec = spec[cols]
    if max_cols is not None and spec.shape[1] > max_cols:
        # keep the most discriminative columns overall
        order = spec.abs().max(axis=0).sort_values(ascending=False).head(max_cols).index
        spec = spec[list(order)]
    lim = float(np.abs(spec.to_numpy()).max()) or 1.0
    fig = go.Figure(
        go.Heatmap(
            z=spec.to_numpy(),
            x=[str(c).replace("_", " ").title() for c in spec.columns],
            y=[str(i) for i in spec.index],
            colorscale=colorscale,
            zmid=0,
            zmin=-lim,
            zmax=lim,
            colorbar=dict(title="rel.", thickness=12),
            hovertemplate="%{y}<br>%{x}<br>%{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        height=max(360, 18 * spec.shape[0] + 140),
        xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
    )
    return _fig(fig)


def tf_figure(slug: str) -> dict[str, Any] | None:
    tf = data.tf_activity(slug)
    if tf is None:
        return None
    return _specificity_heatmap(
        tf, f"{slug.replace('_', ' ')} — TF activity (specificity)", 3, "RdBu_r"
    )


GSEA_LABELS = {
    "hallmark": "Hallmark",
    "kegg": "KEGG",
    "go_bp": "GO biological process",
    "oncogenic": "Oncogenic signature",
    "immunologic": "Immunologic signature",
    "tft": "TF targets",
}


def gsea_figure(slug: str, collection: str = "hallmark") -> dict[str, Any] | None:
    gs = data.gsea(slug, collection)
    if gs is None:
        return None
    label = GSEA_LABELS.get(collection, collection)
    # small collections: show all; large ones: top-3 per cell type, capped at 40
    small = gs.shape[1] <= 60
    return _specificity_heatmap(
        gs,
        f"{slug.replace('_', ' ')} — {label} (specificity)",
        None if small else 3,
        "RdBu_r",
        max_cols=None if small else 40,
    )


def cci_figure(slug: str) -> dict[str, Any] | None:
    """Cell-cell communication matrix: source x target total interaction strength."""
    df = data.cci(slug)
    if df is None:
        return None
    pivot = df.groupby(["source", "target"])["score"].sum().unstack(fill_value=0.0)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.to_numpy(),
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="Viridis",
            colorbar=dict(title="strength", thickness=12),
            hovertemplate="source %{y}<br>target %{x}<br>strength %{z:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{slug.replace('_', ' ')} — cell-cell communication (ligand→receptor)",
        height=max(420, 16 * pivot.shape[0] + 160),
        xaxis=dict(title="target (receptor)", tickangle=-45, tickfont=dict(size=9)),
        yaxis=dict(title="source (ligand)", tickfont=dict(size=9), autorange="reversed"),
    )
    return _fig(fig)
