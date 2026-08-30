"""Organ Browser - overview of each organ atlas.

Per organ: meta (datasets, donors, assays), cell-type composition, and how much
of the composition is organ-specific vs. shared across organs. See docs/CONCEPT.md.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from cella.api import data, plots
from cella.api.schemas import (
    CompositionRow,
    GeneExpressionRow,
    InteractionRow,
    OrganDetail,
    OrganEmbedding,
    OrganGeneExpression,
    OrganMarkerRow,
    OrganSummary,
    PathwayRow,
    StackedComposition,
    TFActivityRow,
)

router = APIRouter(prefix="/organs", tags=["organ-browser"])


def _slug(organ: str) -> str:
    return organ.replace(" ", "_")


def _feature_symbol(feature: str) -> str:
    """Var names are 'SYMBOL_ENSG...'; return the leading gene symbol."""
    return feature.split("_ENSG")[0]


@router.get("", response_model=list[OrganSummary])
def list_organs() -> list[OrganSummary]:
    """The 12 organ atlases with headline counts."""
    df = data.organs().sort_values("n_cells", ascending=False)
    return [
        OrganSummary(
            organ=r["organ"],
            slug=_slug(r["organ"]),
            n_cells=int(r["n_cells"]),
            n_cell_types=int(r["n_cell_types"]),
            n_datasets=int(r["n_datasets"]),
            n_donors=int(r["n_donors"]),
        )
        for r in df.to_dict("records")
    ]


@router.get("/{slug}", response_model=OrganDetail)
def get_organ(slug: str) -> OrganDetail:
    """Meta + cell-type composition for one organ."""
    df = data.organs()
    df = df[df["organ"].map(_slug) == slug]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"unknown organ: {slug}")
    r = df.iloc[0]
    organ = str(r["organ"])
    n_cells = int(r["n_cells"])

    # Composition from the harmonized per-organ table, annotated with shared-ness.
    cto = data.cell_type_organ()
    reg = data.registry().set_index("cl_id")["n_organs"].to_dict()
    rows = cto[cto["organ"] == organ].sort_values("cell_count", ascending=False)
    composition = [
        CompositionRow(
            cl_id=(c["cl_id"] if c["cl_id"] is not None else None),
            ontology_label=c.get("ontology_label"),
            curated_label=c["curated_label"],
            cell_count=int(c["cell_count"]),
            pct=round(100 * c["cell_count"] / n_cells, 2),
            n_organs=int(reg.get(c["cl_id"], 1)),
        )
        for c in rows.to_dict("records")
    ]

    def _split(v: object) -> list[str]:
        return [s for s in str(v).split(" | ") if s] if v else []

    return OrganDetail(
        organ=organ,
        slug=slug,
        n_cells=n_cells,
        n_cell_types=int(r["n_cell_types"]),
        n_datasets=int(r["n_datasets"]),
        n_donors=int(r["n_donors"]),
        n_assays=int(r.get("n_assays", 0)),
        datasets=_split(r.get("datasets_list")),
        assays=_split(r.get("assays_list")),
        composition=composition,
        has_expression=data.expression(slug, "mean") is not None,
    )


@router.get("/{slug}/composition-by", response_model=StackedComposition)
def composition_by(slug: str, group: str = "Dataset") -> StackedComposition:
    """Cell-type proportions within each group (e.g. dataset) for a stacked bar."""
    from cella.pipeline.extract import MODEL_LABEL_COL

    obs = data.obs(slug)
    if group not in obs.columns:
        raise HTTPException(status_code=400, detail=f"unknown group column: {group}")
    tab = (
        obs.groupby([group, MODEL_LABEL_COL], observed=True)
        .size()
        .unstack(fill_value=0)
    )
    frac = tab.div(tab.sum(axis=1), axis=0).fillna(0.0)
    return StackedComposition(
        group_by=group,
        groups=[str(g) for g in frac.index],
        cell_types=[str(c) for c in frac.columns],
        data=frac.round(4).values.tolist(),
    )


@router.get("/{slug}/fig/{kind}")
def organ_figure(
    slug: str, kind: str, collection: str = "hallmark", genes: str = ""
) -> dict:
    """Interactive Plotly figure (JSON): umap | tf | gsea | cci | signature."""
    if kind == "gsea":
        fig = plots.gsea_figure(slug, collection)
    elif kind == "signature":
        fig = plots.signature_umap_figure(slug, _parse_genes(genes))
    elif kind == "gene":
        fig = plots.gene_umap_figure(slug, genes.strip())
    else:
        builders = {
            "umap": plots.umap_figure,
            "tf": plots.tf_figure,
            "cci": plots.cci_figure,
        }
        if kind not in builders:
            raise HTTPException(status_code=404, detail=f"unknown figure: {kind}")
        fig = builders[kind](slug)
    if fig is None:
        raise HTTPException(status_code=404, detail=f"no {kind} data for {slug}")
    return fig


def _parse_genes(genes: str) -> list[str]:
    return [g.strip().upper() for g in genes.replace(",", " ").split() if g.strip()]


@router.get("/{slug}/signature")
def organ_signature(slug: str, genes: str) -> dict:
    """Per-cell-type signature score + which genes matched."""
    score, present, missing = plots.signature_scores(slug, _parse_genes(genes))
    if score is None:
        raise HTTPException(status_code=404, detail="no matching genes for signature")
    ranked = score.sort_values(ascending=False)
    return {
        "matched": present,
        "missing": missing,
        "scores": [
            {"cell_type": str(ct), "score": round(float(v), 3)}
            for ct, v in ranked.items()
        ],
    }


@router.get("/{slug}/embedding", response_model=OrganEmbedding)
def organ_embedding(slug: str) -> OrganEmbedding:
    """Downsampled UMAP scatter for the organ, colored by cell type (compact columnar)."""
    organ = slug.replace("_", " ")
    df = data.embedding(slug)
    if df is None:
        raise HTTPException(status_code=404, detail=f"no embedding derived for {slug}")
    cats = df["cell_type"].astype("category")
    return OrganEmbedding(
        organ=organ,
        cell_types=list(cats.cat.categories),
        x=df["x"].tolist(),
        y=df["y"].tolist(),
        c=cats.cat.codes.tolist(),
    )


@router.get("/{slug}/tf", response_model=list[TFActivityRow])
def organ_tf(slug: str, top_n: int = 5) -> list[TFActivityRow]:
    """Top active transcription factors per cell type (decoupler ULM over CollecTRI)."""
    tf = data.tf_activity(slug)
    if tf is None:
        raise HTTPException(status_code=404, detail=f"no TF activity derived for {slug}")
    # Rank by specificity: a TF's activity in this cell type minus its mean across
    # all cell types. This surfaces distinctive regulators over ubiquitous ones.
    specificity = tf.sub(tf.mean(axis=0), axis=1)
    rows: list[TFActivityRow] = []
    for ct in tf.index:
        for name in specificity.loc[ct].sort_values(ascending=False).head(top_n).index:
            rows.append(
                TFActivityRow(
                    cell_type=str(ct),
                    tf=str(name),
                    activity=round(float(tf.at[ct, name]), 3),
                )
            )
    return rows


@router.get("/{slug}/cci", response_model=list[InteractionRow])
def organ_cci(slug: str, limit: int = 150) -> list[InteractionRow]:
    """Top ligand-receptor interactions between cell types in this organ."""
    df = data.cci(slug)
    if df is None:
        raise HTTPException(status_code=404, detail=f"no CCI derived for {slug}")
    return [
        InteractionRow(
            source=str(r["source"]),
            target=str(r["target"]),
            ligand=str(r["ligand"]),
            receptor=str(r["receptor"]),
            score=round(float(r["score"]), 3),
        )
        for r in df.head(limit).to_dict("records")
    ]


@router.get("/{slug}/gsea", response_model=list[PathwayRow])
def organ_gsea(slug: str, collection: str = "hallmark", top_n: int = 5) -> list[PathwayRow]:
    """Top cell-type-specific gene sets per cell type for a collection (decoupler ULM)."""
    gs = data.gsea(slug, collection)
    if gs is None:
        raise HTTPException(
            status_code=404, detail=f"no GSEA '{collection}' derived for {slug}"
        )
    specificity = gs.sub(gs.mean(axis=0), axis=1)
    rows: list[PathwayRow] = []
    for ct in gs.index:
        for name in specificity.loc[ct].sort_values(ascending=False).head(top_n).index:
            rows.append(
                PathwayRow(
                    cell_type=str(ct),
                    pathway=str(name).replace("_", " ").title(),
                    score=round(float(gs.at[ct, name]), 3),
                )
            )
    return rows


@router.get("/{slug}/markers", response_model=list[OrganMarkerRow])
def organ_markers(slug: str, top_n: int = 5) -> list[OrganMarkerRow]:
    """Top discriminative genes per cell type for this organ, with % expressing."""
    organ = slug.replace("_", " ")
    mk = data.markers()
    mk = mk[(mk["organ"] == organ) & (mk["direction"] == "positive")]
    if mk.empty:
        raise HTTPException(status_code=404, detail=f"no markers for {slug}")
    mk = mk[mk["rank"] <= top_n].sort_values(["cell_type", "rank"])

    # % expressing from pseudobulk, matched by gene symbol -> feature.
    pct = data.expression(slug, "pct")
    sym_to_feature: dict[str, str] = {}
    if pct is not None:
        for col in pct.columns:
            sym_to_feature.setdefault(_feature_symbol(col).upper(), col)

    rows: list[OrganMarkerRow] = []
    for r in mk.to_dict("records"):
        pct_val: float | None = None
        if pct is not None:
            feat = sym_to_feature.get(str(r["gene"]).upper())
            if feat is not None and r["cell_type"] in pct.index:
                pct_val = round(float(pct.at[r["cell_type"], feat]), 3)
        rows.append(
            OrganMarkerRow(
                cell_type=str(r["cell_type"]),
                gene=str(r["gene"]),
                coef=round(float(r["coef"]), 3),
                pct=pct_val,
            )
        )
    return rows


@router.get("/{slug}/gene/{gene}", response_model=OrganGeneExpression)
def organ_gene_expression(slug: str, gene: str) -> OrganGeneExpression:
    """Mean expression + fraction expressing of one gene across the organ's cell types."""
    organ = slug.replace("_", " ")
    mean = data.expression(slug, "mean")
    pct = data.expression(slug, "pct")
    if mean is None or pct is None:
        raise HTTPException(status_code=404, detail=f"no expression derived for {slug}")

    want = gene.strip().upper()
    matches = [c for c in mean.columns if _feature_symbol(c).upper() == want]
    if not matches:
        return OrganGeneExpression(
            organ=organ, gene=gene, found=False, matched_feature=None, rows=[]
        )
    # if a symbol maps to several Ensembl IDs, take the most-expressed feature
    feature = max(matches, key=lambda c: float(mean[c].sum()))

    rows = [
        GeneExpressionRow(
            cell_type=str(ct),
            mean=round(float(mean.at[ct, feature]), 4),
            pct=round(float(pct.at[ct, feature]), 4),
        )
        for ct in mean.index
    ]
    rows.sort(key=lambda x: x.mean, reverse=True)
    return OrganGeneExpression(
        organ=organ, gene=gene, found=True, matched_feature=feature, rows=rows
    )
