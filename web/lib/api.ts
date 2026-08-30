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
  const params = new URLSearchParams({
    q,
    min_organs: String(minOrgans),
    limit: String(limit),
  });
  return getJSON<CellTypeSummary[]>(`/api/cell-types?${params}`);
}

export function fetchMarkerAtlas(clId: string, topN = 10): Promise<MarkerAtlas> {
  return getJSON<MarkerAtlas>(
    `/api/markers/${encodeURIComponent(clId)}?top_n=${topN}`,
  );
}

export function fetchFingerprint(clId: string, topN = 10): Promise<Fingerprint> {
  return getJSON<Fingerprint>(
    `/api/fingerprints/${encodeURIComponent(clId)}?top_n=${topN}`,
  );
}

export function fetchGeneAcrossOrgans(
  clId: string,
  gene: string,
): Promise<GeneAcrossOrgans> {
  return getJSON<GeneAcrossOrgans>(
    `/api/fingerprints/${encodeURIComponent(clId)}/gene/${encodeURIComponent(gene)}`,
  );
}

export function reverseLookup(
  genes: string,
  organ?: string,
  limit = 15,
): Promise<ReverseLookup> {
  const params = new URLSearchParams({ genes, limit: String(limit) });
  if (organ) params.set("organ", organ);
  return getJSON<ReverseLookup>(`/api/reverse-lookup?${params}`);
}

export function fetchGraph(
  organ?: string,
  minSimilarity = 0,
): Promise<RelationshipGraph> {
  const params = new URLSearchParams({ min_similarity: String(minSimilarity) });
  if (organ) params.set("organ", organ);
  return getJSON<RelationshipGraph>(`/api/graph?${params}`);
}

export function fetchEdgeDetail(
  sourceId: string,
  targetId: string,
): Promise<EdgeDetail> {
  return getJSON<EdgeDetail>(
    `/api/graph/edge/${encodeURIComponent(sourceId)}/${encodeURIComponent(targetId)}`,
  );
}

export function listOrgans(): Promise<OrganSummary[]> {
  return getJSON<OrganSummary[]>("/api/organs");
}

export function fetchOrgan(slug: string): Promise<OrganDetail> {
  return getJSON<OrganDetail>(`/api/organs/${encodeURIComponent(slug)}`);
}

export function fetchOrganEmbedding(slug: string): Promise<OrganEmbedding> {
  return getJSON<OrganEmbedding>(
    `/api/organs/${encodeURIComponent(slug)}/embedding`,
  );
}

export function fetchOrganGene(
  slug: string,
  gene: string,
): Promise<OrganGeneExpression> {
  return getJSON<OrganGeneExpression>(
    `/api/organs/${encodeURIComponent(slug)}/gene/${encodeURIComponent(gene)}`,
  );
}

export function fetchOrganMarkers(
  slug: string,
  topN = 5,
): Promise<OrganMarkerRow[]> {
  return getJSON<OrganMarkerRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/markers?top_n=${topN}`,
  );
}

export function fetchOrganComposition(
  slug: string,
  group = "Dataset",
): Promise<StackedComposition> {
  return getJSON<StackedComposition>(
    `/api/organs/${encodeURIComponent(slug)}/composition-by?group=${encodeURIComponent(group)}`,
  );
}

export function fetchOrganTF(slug: string, topN = 5): Promise<TFActivityRow[]> {
  return getJSON<TFActivityRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/tf?top_n=${topN}`,
  );
}

export function fetchOrganGSEA(
  slug: string,
  collection = "hallmark",
  topN = 5,
): Promise<PathwayRow[]> {
  return getJSON<PathwayRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/gsea?collection=${collection}&top_n=${topN}`,
  );
}

export function fetchOrganCCI(slug: string, limit = 150): Promise<InteractionRow[]> {
  return getJSON<InteractionRow[]>(
    `/api/organs/${encodeURIComponent(slug)}/cci?limit=${limit}`,
  );
}

export function fetchOrganSignature(
  slug: string,
  genes: string,
): Promise<SignatureResult> {
  return getJSON<SignatureResult>(
    `/api/organs/${encodeURIComponent(slug)}/signature?genes=${encodeURIComponent(genes)}`,
  );
}
