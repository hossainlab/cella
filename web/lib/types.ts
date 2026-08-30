// Mirrors cella.api.schemas.

export interface CellTypeSummary {
  cl_id: string;
  ontology_label: string;
  n_organs: number;
  total_cells: number;
}

export interface GeneWeight {
  gene: string;
  coef: number;
  rank: number;
}

export interface OrganMarkers {
  organ: string;
  positive: GeneWeight[];
  negative: GeneWeight[];
}

export interface SharedGene {
  gene: string;
  n_organs: number;
}

export interface OrganSummary {
  organ: string;
  slug: string;
  n_cells: number;
  n_cell_types: number;
  n_datasets: number;
  n_donors: number;
}

export interface CompositionRow {
  cl_id: string | null;
  ontology_label: string | null;
  curated_label: string;
  cell_count: number;
  pct: number;
  n_organs: number;
}

export interface OrganDetail extends OrganSummary {
  n_assays: number;
  datasets: string[];
  assays: string[];
  composition: CompositionRow[];
  has_expression: boolean;
}

export interface OrganEmbedding {
  organ: string;
  cell_types: string[];
  x: number[];
  y: number[];
  c: number[];
}

export interface GeneExpressionRow {
  cell_type: string;
  mean: number;
  pct: number;
}

export interface OrganGeneExpression {
  organ: string;
  gene: string;
  found: boolean;
  matched_feature: string | null;
  rows: GeneExpressionRow[];
}

export interface OrganMarkerRow {
  cell_type: string;
  gene: string;
  coef: number;
  pct: number | null;
}

export interface StackedComposition {
  group_by: string;
  groups: string[];
  cell_types: string[];
  data: number[][];
}

export interface TFActivityRow {
  cell_type: string;
  tf: string;
  activity: number;
}

export interface PathwayRow {
  cell_type: string;
  pathway: string;
  score: number;
}

export interface InteractionRow {
  source: string;
  target: string;
  ligand: string;
  receptor: string;
  score: number;
}

export interface SignatureResult {
  matched: string[];
  missing: string[];
  scores: { cell_type: string; score: number }[];
}

export interface FingerprintCell {
  organ: string;
  coef: number;
  rank: number;
  direction: string;
}

export interface FingerprintGene {
  gene: string;
  n_organs: number;
  max_abs: number;
  cells: FingerprintCell[];
}

export interface Fingerprint {
  cl_id: string;
  ontology_label: string;
  organs: string[];
  per_organ: OrganMarkers[];
  genes: FingerprintGene[];
}

export interface GeneOrganWeight {
  organ: string;
  coef: number;
  rank: number;
  direction: string;
}

export interface GeneAcrossOrgans {
  cl_id: string;
  ontology_label: string;
  gene: string;
  present_in: GeneOrganWeight[];
  absent_in: string[];
}

export interface SignatureGene {
  gene: string;
  coef: number;
}

export interface SignatureHit {
  cl_id: string | null;
  ontology_label: string;
  curated_label: string;
  organ: string;
  score: number;
  n_matched: number;
  top_genes: SignatureGene[];
}

export interface ReverseLookup {
  query_genes: string[];
  matched_genes: string[];
  unknown_genes: string[];
  hits: SignatureHit[];
  is_confident: boolean;
  note: string;
}

export interface GraphNode {
  cl_id: string;
  label: string;
  n_organs: number;
  total_cells: number;
  primary_organ: string;
  x: number;
  y: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  similarity: number;
}

export interface RelationshipGraph {
  organs: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  n_total_nodes: number;
}

export interface SharedEdgeGene {
  gene: string;
  source_coef: number;
  target_coef: number;
}

export interface EdgeDetail {
  source: GraphNode;
  target: GraphNode;
  similarity: number;
  shared_genes: SharedEdgeGene[];
}

export interface MarkerAtlas {
  cl_id: string;
  ontology_label: string;
  organs: string[];
  per_organ: OrganMarkers[];
  shared_genes: SharedGene[];
  consensus_genes: string[];
  organ_specific: Record<string, string[]>;
}
