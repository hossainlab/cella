"""Pydantic response schemas shared by the API routers."""

from __future__ import annotations

from pydantic import BaseModel


class CellTypeSummary(BaseModel):
    cl_id: str
    ontology_label: str
    n_organs: int
    total_cells: int


class OrganPresence(BaseModel):
    organ: str
    curated_label: str
    cell_count: int


class CellTypeDetail(CellTypeSummary):
    organs: list[str]
    aliases: list[str]
    presence: list[OrganPresence]


class GeneWeight(BaseModel):
    gene: str
    coef: float
    rank: int


class OrganMarkers(BaseModel):
    organ: str
    positive: list[GeneWeight]
    negative: list[GeneWeight]


class SharedGene(BaseModel):
    gene: str
    n_organs: int  # how many organs this gene is a top marker in


class OrganSummary(BaseModel):
    organ: str
    slug: str
    n_cells: int
    n_cell_types: int
    n_datasets: int
    n_donors: int


class CompositionRow(BaseModel):
    cl_id: str | None
    ontology_label: str | None
    curated_label: str
    cell_count: int
    pct: float  # share of the organ's cells
    n_organs: int  # how many organs this cell type appears in (shared-ness)


class OrganDetail(OrganSummary):
    n_assays: int
    datasets: list[str]
    assays: list[str]
    composition: list[CompositionRow]
    has_expression: bool  # whether pseudobulk expression is derived for this organ


class OrganEmbedding(BaseModel):
    organ: str
    cell_types: list[str]  # legend categories
    x: list[float]
    y: list[float]
    c: list[int]  # per-point index into cell_types


class GeneExpressionRow(BaseModel):
    cell_type: str
    mean: float  # mean log-normalized expression
    pct: float  # fraction of cells expressing (0-1)


class OrganGeneExpression(BaseModel):
    organ: str
    gene: str
    found: bool
    matched_feature: str | None
    rows: list[GeneExpressionRow]


class OrganMarkerRow(BaseModel):
    cell_type: str
    gene: str
    coef: float  # discriminative weight (analogous to a differential score)
    pct: float | None  # fraction of the cell type's cells expressing it


class TFActivityRow(BaseModel):
    cell_type: str
    tf: str
    activity: float  # ULM activity score (signed)


class PathwayRow(BaseModel):
    cell_type: str
    pathway: str
    score: float  # ULM activity over the Hallmark gene set (signed)


class InteractionRow(BaseModel):
    source: str  # ligand-sending cell type
    target: str  # receptor-bearing cell type
    ligand: str
    receptor: str
    score: float


class StackedComposition(BaseModel):
    group_by: str  # e.g. "Dataset"
    groups: list[str]  # x-axis categories
    cell_types: list[str]  # stack segments
    data: list[list[float]]  # data[group_index][cell_type_index] = fraction (0-1)


class FingerprintCell(BaseModel):
    """One gene's signed discriminative weight in one organ (heatmap cell)."""

    organ: str
    coef: float  # signed classifier weight (positive = up-defining, negative = down)
    rank: int  # rank within its direction in that organ
    direction: str  # "positive" | "negative"


class FingerprintGene(BaseModel):
    """A gene pivoted across organs — one row of the fingerprint heatmap."""

    gene: str
    n_organs: int  # organs where it is a top signed marker of this type
    max_abs: float  # strongest |weight| across organs (for row sorting)
    cells: list[FingerprintCell]  # one per organ where it is a top marker


class Fingerprint(BaseModel):
    cl_id: str
    ontology_label: str
    organs: list[str]  # organs the cell type appears in
    per_organ: list[OrganMarkers]  # top +/- signed weights per organ
    genes: list[FingerprintGene]  # union of top +/- genes, pivoted for the heatmap


class GeneOrganWeight(BaseModel):
    organ: str
    coef: float
    rank: int
    direction: str


class GeneAcrossOrgans(BaseModel):
    """One gene's discriminative weight for a cell type across every organ."""

    cl_id: str
    ontology_label: str
    gene: str
    present_in: list[GeneOrganWeight]  # organs where it is a top signed marker
    absent_in: list[str]  # organs the type appears in but the gene is not a top marker


class SignatureGene(BaseModel):
    gene: str
    pct: float  # fraction of this cell type's cells expressing the gene, in this organ
    coef: float | None  # discriminative weight, if the gene is in the organ's model


class SignatureHit(BaseModel):
    cl_id: str | None  # harmonized id, if the curated type is ontology-mapped
    ontology_label: str  # harmonized label (falls back to curated label)
    curated_label: str  # the organ-specific label the model was trained on
    organ: str
    score: float  # mean fraction of cells expressing the matched query genes
    n_matched: int  # query genes present in this organ's expression vocabulary
    top_genes: list[SignatureGene]  # most widely expressed matched genes


class ReverseLookup(BaseModel):
    """Which cell type does a gene signature define? (reverse of the Marker Atlas)."""

    query_genes: list[str]
    matched_genes: list[str]  # query genes found in at least one organ
    unknown_genes: list[str]  # query genes absent from every organ's vocabulary
    hits: list[SignatureHit]  # best-matching (organ, cell type), strongest first
    is_confident: bool  # whether the top hit clears the match threshold
    note: str  # plain-language verdict, including the novelty caveat


class GraphNode(BaseModel):
    cl_id: str
    label: str
    n_organs: int
    total_cells: int
    primary_organ: str  # organ contributing the most cells (drives node color)
    x: float
    y: float


class GraphEdge(BaseModel):
    source: str  # cl_id
    target: str  # cl_id
    similarity: float  # cosine similarity of the two weight vectors (0-1)


class RelationshipGraph(BaseModel):
    organs: list[str]  # every organ present, for the filter UI
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    n_total_nodes: int  # nodes before organ filtering (for a "showing X of Y" note)


class SharedEdgeGene(BaseModel):
    gene: str
    source_coef: float
    target_coef: float


class EdgeDetail(BaseModel):
    source: GraphNode
    target: GraphNode
    similarity: float
    shared_genes: list[SharedEdgeGene]  # top genes defining both types (edge basis)


class MarkerAtlas(BaseModel):
    cl_id: str
    ontology_label: str
    organs: list[str]
    per_organ: list[OrganMarkers]
    shared_genes: list[SharedGene]  # top marker in >=2 organs, most-shared first
    consensus_genes: list[str]  # the strict subset: top marker in every organ
    organ_specific: dict[str, list[str]]  # gene is a top marker in exactly one organ
