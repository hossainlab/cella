import type {
  CellTypeSummary,
  EdgeDetail,
  Fingerprint,
  GeneAcrossOrgans,
  InteractionRow,
  MarkerAtlas,
  RelationshipGraph,
  OrganDetail,
  OrganEmbedding,
  OrganGeneExpression,
  OrganMarkerRow,
  OrganSummary,
  PathwayRow,
  ReverseLookup,
  SignatureResult,
  StackedComposition,
  TFActivityRow,
} from "./types";
import * as S from "./static";

/**
 * Data source, fixed at build time. "server" (default) calls the FastAPI backend
 * through the /api proxy; "static" reads files written by `cella export` and
 * computes free-text queries in the browser (see lib/static.ts). Every function
 * below has the same signature and result in both modes.
 */
export const STATIC_MODE = process.env.NEXT_PUBLIC_DATA_MODE === "static";
const enc = encodeURIComponent;

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function searchCellTypes(
  q: string,
  minOrgans = 1,
  limit = 50,
): Promise<CellTypeSummary[]> {
  if (STATIC_MODE) return S.searchCellTypes(q, minOrgans, limit);
  const params = new URLSearchParams({
    q,
    min_organs: String(minOrgans),
    limit: String(limit),
  });
  return getJSON<CellTypeSummary[]>(`/api/cell-types?${params}`);
}

export function fetchMarkerAtlas(
  clId: string,
  topN = 10,
): Promise<MarkerAtlas> {
  if (STATIC_MODE) return S.staticJSON(`markers/${S.clFile(clId)}.json`);
  return getJSON<MarkerAtlas>(
    `/api/markers/${encodeURIComponent(clId)}?top_n=${topN}`,
  );
}

export function fetchFingerprint(
  clId: string,
  topN = 10,
): Promise<Fingerprint> {
  if (STATIC_MODE) return S.staticJSON(`fingerprints/${S.clFile(clId)}.json`);
  return getJSON<Fingerprint>(
    `/api/fingerprints/${encodeURIComponent(clId)}?top_n=${topN}`,
  );
}

export function fetchGeneAcrossOrgans(
  clId: string,
  gene: string,
): Promise<GeneAcrossOrgans> {
  if (STATIC_MODE) return S.geneAcrossOrgans(clId, gene);
  return getJSON<GeneAcrossOrgans>(
    `/api/fingerprints/${encodeURIComponent(clId)}/gene/${encodeURIComponent(gene)}`,
  );
}

export function reverseLookup(
  genes: string,
  organ?: string,
  limit = 15,
): Promise<ReverseLookup> {
  if (STATIC_MODE) return S.reverseLookup(genes, organ, limit);
  const params = new URLSearchParams({ genes, limit: String(limit) });
  if (organ) params.set("organ", organ);
  return getJSON<ReverseLookup>(`/api/reverse-lookup?${params}`);
}

export function fetchGraph(
  organ?: string,
  minSimilarity = 0,
): Promise<RelationshipGraph> {
  if (STATIC_MODE) return S.graph(organ, minSimilarity);
  const params = new URLSearchParams({ min_similarity: String(minSimilarity) });
  if (organ) params.set("organ", organ);
  return getJSON<RelationshipGraph>(`/api/graph?${params}`);
}

export function fetchEdgeDetail(
  sourceId: string,
  targetId: string,
): Promise<EdgeDetail> {
  if (STATIC_MODE) return S.edgeDetail(sourceId, targetId);
  return getJSON<EdgeDetail>(
    `/api/graph/edge/${encodeURIComponent(sourceId)}/${encodeURIComponent(targetId)}`,
  );
}

export function listOrgans(): Promise<OrganSummary[]> {
  if (STATIC_MODE) return S.staticJSON("organs.json");
  return getJSON<OrganSummary[]>("/api/organs");
}

export function fetchOrgan(slug: string): Promise<OrganDetail> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/detail.json`);
  return getJSON<OrganDetail>(`/api/organs/${encodeURIComponent(slug)}`);
}

export function fetchOrganEmbedding(slug: string): Promise<OrganEmbedding> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/embedding.json`);
  return getJSON<OrganEmbedding>(
    `/api/organs/${encodeURIComponent(slug)}/embedding`,
  );
}

export function fetchOrganGene(
  slug: string,
  gene: string,
): Promise<OrganGeneExpression> {
  if (STATIC_MODE) return S.organGene(slug, gene);
  return getJSON<OrganGeneExpression>(
    `/api/organs/${encodeURIComponent(slug)}/gene/${encodeURIComponent(gene)}`,
  );
}

export function fetchOrganMarkers(
  slug: string,
  topN = 5,
): Promise<OrganMarkerRow[]> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/markers.json`);
  return getJSON<OrganMarkerRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/markers?top_n=${topN}`,
  );
}

export function fetchOrganComposition(
  slug: string,
  group = "Dataset",
): Promise<StackedComposition> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/composition.json`);
  return getJSON<StackedComposition>(
    `/api/organs/${encodeURIComponent(slug)}/composition-by?group=${encodeURIComponent(group)}`,
  );
}

export function fetchOrganTF(slug: string, topN = 5): Promise<TFActivityRow[]> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/tf.json`);
  return getJSON<TFActivityRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/tf?top_n=${topN}`,
  );
}

export function fetchOrganGSEA(
  slug: string,
  collection = "hallmark",
  topN = 5,
): Promise<PathwayRow[]> {
  if (STATIC_MODE)
    return S.staticJSON(`organs/${slug}/gsea-${collection}.json`);
  return getJSON<PathwayRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/gsea?collection=${collection}&top_n=${topN}`,
  );
}

export function fetchOrganCCI(
  slug: string,
  limit = 150,
): Promise<InteractionRow[]> {
  if (STATIC_MODE) return S.staticJSON(`organs/${slug}/cci.json`);
  return getJSON<InteractionRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/cci?limit=${limit}`,
  );
}

export function fetchOrganSignature(
  slug: string,
  genes: string,
): Promise<SignatureResult> {
  if (STATIC_MODE) return S.organSignature(slug, genes);
  return getJSON<SignatureResult>(
    `/api/organs/${encodeURIComponent(slug)}/signature?genes=${encodeURIComponent(genes)}`,
  );
}

/** Plotly figure for the Organ Browser (GET /organs/{slug}/fig/{kind}). */
export function fetchOrganFigure(
  slug: string,
  kind: S.FigureKind,
  opts: { collection?: string; genes?: string } = {},
): Promise<{ data: unknown[]; layout: Record<string, unknown> }> {
  if (STATIC_MODE) return S.figure(slug, kind, opts);
  const params = new URLSearchParams();
  if (opts.collection) params.set("collection", opts.collection);
  if (opts.genes) params.set("genes", opts.genes);
  const qs = params.toString();
  return getJSON(`/api/organs/${enc(slug)}/fig/${kind}${qs ? `?${qs}` : ""}`);
}
