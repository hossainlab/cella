/**
 * Static data mode: the site runs with no backend (e.g. GitHub Pages).
 *
 * Fixed-input responses are files written by `cella export`
 * (src/cella/api/export.py, which documents the layout); they are the server's
 * own responses, so this module only maps a request to its file. Endpoints that
 * take free text are re-implemented here against the compact expression tables,
 * mirroring the Python handlers named in each function's comment.
 */

import type {
  CellTypeSummary,
  EdgeDetail,
  GeneAcrossOrgans,
  GeneOrganWeight,
  OrganGeneExpression,
  RelationshipGraph,
  ReverseLookup,
  SignatureGene,
  SignatureHit,
  SignatureResult,
} from "./types";
import { ORGANS, organSlug } from "./organs";

export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const DATA = `${BASE_PATH}/data`;

export const clFile = (clId: string) => clId.replace(/:/g, "_");
export const slugOf = organSlug;

const jsonCache = new Map<string, Promise<unknown>>();

/** Fetch a static JSON file once per page session. 404 surfaces like a server 404. */
export function staticJSON<T>(rel: string): Promise<T> {
  let p = jsonCache.get(rel);
  if (!p) {
    p = fetch(`${DATA}/${rel}`).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status}: no data for ${rel}`);
      return res.json();
    });
    p.catch(() => jsonCache.delete(rel));
    jsonCache.set(rel, p);
  }
  return p as Promise<T>;
}

// ---------------------------------------------------------------- expression

interface ExprMeta {
  organ: string;
  labels: string[];
  genes: string[]; // genes with a stored value, column order of the binaries
  zero_genes: string[]; // in the vocabulary but expressed nowhere in the organ
  mean_scale: number;
}

export interface ExprTable {
  organ: string;
  labels: string[];
  genes: string[]; // original-case symbols
  geneIndex: Map<string, number>; // UPPER-cased stored gene -> column
  vocab: Map<string, string>; // UPPER-cased stored + zero genes -> original symbol
  pct: Uint8Array; // labels x genes, value / 255
  mean: Uint16Array; // labels x genes, value / 65535 * meanScale
  meanScale: number;
}

async function gunzip(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok || !res.body) throw new Error(`${res.status}: ${url}`);
  const stream = res.body.pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

const exprCache = new Map<string, Promise<ExprTable | null>>();

/** One organ's expression tables, or null if the organ has none derived. */
export function loadExpr(
  slug: string,
  withMean = true,
): Promise<ExprTable | null> {
  const key = `${slug}:${withMean}`;
  let p = exprCache.get(key);
  if (!p) {
    p = (async () => {
      let meta: ExprMeta;
      try {
        meta = await staticJSON<ExprMeta>(`expr/${slug}.json`);
      } catch {
        return null;
      }
      const [pctBuf, meanBuf] = await Promise.all([
        gunzip(`${DATA}/expr/${slug}.pct.bin.gz`),
        withMean
          ? gunzip(`${DATA}/expr/${slug}.mean.bin.gz`)
          : Promise.resolve(null),
      ]);
      return {
        organ: meta.organ,
        labels: meta.labels,
        genes: meta.genes,
        geneIndex: new Map(meta.genes.map((g, i) => [g.toUpperCase(), i])),
        vocab: new Map(
          [...meta.genes, ...meta.zero_genes].map((g) => [g.toUpperCase(), g]),
        ),
        pct: new Uint8Array(pctBuf),
        mean: meanBuf ? new Uint16Array(meanBuf) : new Uint16Array(0),
        meanScale: meta.mean_scale,
      };
    })();
    p.catch(() => exprCache.delete(key));
    exprCache.set(key, p);
  }
  return p;
}

const pctAt = (t: ExprTable, row: number, col: number | undefined) =>
  col === undefined ? 0 : t.pct[row * t.genes.length + col] / 255;
const meanAt = (t: ExprTable, row: number, col: number | undefined) =>
  col === undefined
    ? 0
    : (t.mean[row * t.genes.length + col] / 65535) * t.meanScale;

const round = (x: number, d: number) => Math.round(x * 10 ** d) / 10 ** d;

/** routers/reverse_lookup.py::_parse_genes: split on commas/whitespace/semicolons, upper, dedupe. */
export function parseGenes(raw: string): string[] {
  const seen = new Set<string>();
  for (const tok of raw.trim().split(/[\s,;]+/)) {
    const g = tok.trim().toUpperCase();
    if (g) seen.add(g);
  }
  return [...seen];
}

/** routers/organs.py::_parse_genes: commas to spaces, split on whitespace, upper (no dedupe). */
function parseSignatureGenes(raw: string): string[] {
  return raw
    .replace(/,/g, " ")
    .split(/\s+/)
    .map((g) => g.trim().toUpperCase())
    .filter(Boolean);
}

// ------------------------------------------------------- free-text endpoints

/** Mirrors routers/organs.py::organ_gene_expression. */
export async function organGene(
  slug: string,
  gene: string,
): Promise<OrganGeneExpression> {
  const t = await loadExpr(slug);
  const organ = slug.replace(/_/g, " ");
  if (!t) throw new Error(`404: no expression derived for ${slug}`);
  const want = gene.trim().toUpperCase();
  const feature = t.vocab.get(want);
  if (feature === undefined) {
    return { organ, gene, found: false, matched_feature: null, rows: [] };
  }
  const col = t.geneIndex.get(want);
  const rows = t.labels.map((ct, r) => ({
    cell_type: ct,
    mean: round(meanAt(t, r, col), 4),
    pct: round(pctAt(t, r, col), 4),
  }));
  rows.sort((a, b) => b.mean - a.mean);
  return { organ, gene, found: true, matched_feature: feature, rows };
}

/** Mirrors plots.py::signature_scores (mean of per-gene z-scored means). */
export async function signatureScores(
  slug: string,
  genes: string[],
): Promise<{
  scores: Map<string, number>;
  present: string[];
  missing: string[];
} | null> {
  const t = await loadExpr(slug);
  if (!t) return null;
  const present = genes.filter((g) => t.vocab.has(g));
  const missing = genes.filter((g) => !t.vocab.has(g));
  if (!present.length) return { scores: new Map(), present, missing };
  const n = t.labels.length;
  const total = new Float64Array(n);
  for (const g of present) {
    const col = t.geneIndex.get(g);
    const v = Array.from({ length: n }, (_, r) => meanAt(t, r, col));
    const mu = v.reduce((a, b) => a + b, 0) / n;
    // pandas .std() is the sample SD (ddof=1); zero SD -> 1, as in Python.
    const sd =
      Math.sqrt(
        v.reduce((a, b) => a + (b - mu) ** 2, 0) / Math.max(n - 1, 1),
      ) || 1;
    v.forEach((x, r) => (total[r] += (x - mu) / sd));
  }
  const scores = new Map(
    t.labels.map((ct, r) => [ct, total[r] / present.length]),
  );
  return { scores, present, missing };
}

/** Mirrors routers/organs.py::organ_signature. */
export async function organSignature(
  slug: string,
  raw: string,
): Promise<SignatureResult> {
  const res = await signatureScores(slug, parseSignatureGenes(raw));
  if (!res || !res.present.length)
    throw new Error("404: no matching genes for signature");
  const scores = [...res.scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([cell_type, s]) => ({ cell_type, score: round(s, 3) }));
  return { matched: res.present, missing: res.missing, scores };
}

interface CellTypeOrganRow {
  organ: string;
  curated_label: string;
  cl_id: string | null;
  ontology_label: string | null;
}

// Mirrors the constants in routers/reverse_lookup.py.
const MIN_SCORE = 0.3;
const MIN_MARGIN = 0.1;

/** Mirrors routers/reverse_lookup.py::reverse_lookup. */
export async function reverseLookup(
  raw: string,
  organ: string | undefined,
  limit: number,
): Promise<ReverseLookup> {
  const query = parseGenes(raw);
  if (!query.length) throw new Error("400: no genes provided");
  if (query.length > 200) throw new Error("400: too many genes (max 200)");

  const organs = organ ? [organ] : ORGANS;
  const [cto, relatives, tables] = await Promise.all([
    staticJSON<CellTypeOrganRow[]>("cell-type-organ.json"),
    staticJSON<Record<string, string[]>>("cl-relatives.json"),
    Promise.all(organs.map((o) => loadExpr(slugOf(o), false))),
  ]);
  const labelMap = new Map(
    cto.map((r) => [
      `${r.organ}|${r.curated_label}`,
      [r.cl_id, r.ontology_label ?? r.curated_label],
    ]),
  );
  // Classifier weights are evidence only; fetched lazily per organ with a top hit.
  const matched = new Set<string>();
  const hits: SignatureHit[] = [];

  organs.forEach((org, i) => {
    const t = tables[i];
    if (!t) return;
    const present = query.filter((g) => t.vocab.has(g));
    if (!present.length) return;
    present.forEach((g) => matched.add(g));
    const cols = present.map((g) => t.geneIndex.get(g));
    t.labels.forEach((label, r) => {
      const fracs = cols.map((c) => pctAt(t, r, c));
      const score = fracs.reduce((a, b) => a + b, 0) / fracs.length;
      const top: SignatureGene[] = present
        .map((g, j) => ({ gene: g, pct: fracs[j], coef: null }))
        .sort((a, b) => b.pct - a.pct)
        .slice(0, 5);
      const [clId, onto] = labelMap.get(`${org}|${label}`) ?? [null, label];
      hits.push({
        cl_id: clId ?? null,
        ontology_label: onto ?? label,
        curated_label: label,
        organ: org,
        score,
        n_matched: present.length,
        top_genes: top,
      });
    });
  });

  if (!hits.length) {
    return {
      query_genes: query,
      matched_genes: [],
      unknown_genes: query,
      hits: [],
      is_confident: false,
      note: "None of these genes are in the atlas gene vocabulary.",
    };
  }

  hits.sort((a, b) => b.score - a.score);
  const topHits = hits.slice(0, limit);
  const best = topHits[0];
  const bestKey = best.cl_id ?? best.ontology_label;
  const allied = new Set([bestKey, ...(relatives[bestKey] ?? [])]);
  const runnerUp =
    hits.find((h) => !allied.has(h.cl_id ?? h.ontology_label))?.score ?? 0;
  const margin = best.score > 0 ? (best.score - runnerUp) / best.score : 0;
  const isConfident =
    best.score >= MIN_SCORE &&
    margin >= MIN_MARGIN &&
    best.n_matched >= Math.min(2, matched.size);

  await attachWeights(topHits);

  const pctFmt = (x: number) => `${Math.round(x * 100)}%`;
  const note = isConfident
    ? `Best match: ${best.ontology_label} in ${best.organ} (${pctFmt(best.score)} of its cells ` +
      `express the query genes on average, ${best.n_matched} of ${query.length} genes ` +
      `recognized; ${pctFmt(margin)} ahead of the next cell type).`
    : "No clear match — no single cell type expresses these genes markedly more than the " +
      "others. Could be a mixed, rare, or novel state, or too few genes recognized.";

  return {
    query_genes: query,
    matched_genes: query.filter((g) => matched.has(g)),
    unknown_genes: query.filter((g) => !matched.has(g)),
    hits: topHits,
    is_confident: isConfident,
    note,
  };
}

interface MarkerRow {
  organ: string;
  gene: string;
  coef: number;
  rank: number;
  direction: string;
}

/**
 * Fill in each hit gene's classifier weight where the static marker rows have it.
 * The server reads the full weight matrix; statically only the stored top-N
 * markers are available, so weights for other genes stay null (hover only).
 */
async function attachWeights(hits: SignatureHit[]): Promise<void> {
  const byCl = new Map<string, MarkerRow[]>();
  await Promise.all(
    [...new Set(hits.map((h) => h.cl_id).filter((c): c is string => !!c))].map(
      async (cl) => {
        try {
          byCl.set(
            cl,
            await staticJSON<MarkerRow[]>(`marker-rows/${clFile(cl)}.json`),
          );
        } catch {
          /* no markers for this term */
        }
      },
    ),
  );
  for (const h of hits) {
    const rows = h.cl_id ? byCl.get(h.cl_id) : undefined;
    if (!rows) continue;
    for (const g of h.top_genes) {
      const r = rows.find(
        (m) => m.organ === h.organ && m.gene.toUpperCase() === g.gene,
      );
      if (r) g.coef = r.coef;
    }
  }
}

// ------------------------------------------------- finite but filtered client-side

/** Mirrors routers/cell_types.py::search_cell_types over the exported registry. */
export async function searchCellTypes(
  q: string,
  minOrgans: number,
  limit: number,
): Promise<CellTypeSummary[]> {
  const all = await staticJSON<CellTypeSummary[]>("cell-types.json");
  const needle = q.toLowerCase();
  return all
    .filter(
      (c) =>
        !needle ||
        c.ontology_label.toLowerCase().includes(needle) ||
        c.cl_id.toLowerCase().includes(needle),
    )
    .filter((c) => c.n_organs >= minOrgans)
    .slice(0, limit);
}

/** Mirrors routers/graph.py::subgraph: the exported graph has every edge; filter here. */
export async function graph(organ: string | undefined, minSimilarity: number) {
  const g = await staticJSON<RelationshipGraph>(
    organ ? `graph/${slugOf(organ)}.json` : "graph/all.json",
  );
  return { ...g, edges: g.edges.filter((e) => e.similarity >= minSimilarity) };
}

/** Mirrors routers/graph.py::edge_detail; files are stored under sorted ids. */
export async function edgeDetail(
  sourceId: string,
  targetId: string,
): Promise<EdgeDetail> {
  const [a, b] = [sourceId, targetId].sort();
  const e = await staticJSON<EdgeDetail>(
    `graph/edge/${clFile(a)}__${clFile(b)}.json`,
  );
  if (e.source.cl_id === sourceId) return e;
  return {
    ...e,
    source: e.target,
    target: e.source,
    shared_genes: e.shared_genes.map((g) => ({
      gene: g.gene,
      source_coef: g.target_coef,
      target_coef: g.source_coef,
    })),
  };
}

/** Mirrors routers/fingerprints.py::gene_across_organs over the exported marker rows. */
export async function geneAcrossOrgans(
  clId: string,
  gene: string,
): Promise<GeneAcrossOrgans> {
  const [rows, types] = await Promise.all([
    staticJSON<MarkerRow[]>(`marker-rows/${clFile(clId)}.json`),
    staticJSON<CellTypeSummary[]>("cell-types.json"),
  ]);
  const label = types.find((c) => c.cl_id === clId)?.ontology_label;
  if (!label) throw new Error(`404: unknown cl_id: ${clId}`);
  if (!rows.length) throw new Error(`404: no markers for cl_id: ${clId}`);
  const organs = [...new Set(rows.map((r) => r.organ))].sort();
  const hits = rows.filter((r) => r.gene.toUpperCase() === gene.toUpperCase());
  const present: GeneOrganWeight[] = [];
  for (const organ of organs) {
    const inOrgan = hits.filter((r) => r.organ === organ);
    if (!inOrgan.length) continue;
    const r = inOrgan.reduce((m, x) =>
      Math.abs(x.coef) > Math.abs(m.coef) ? x : m,
    );
    present.push({ organ, coef: r.coef, rank: r.rank, direction: r.direction });
  }
  present.sort((x, y) => Math.abs(y.coef) - Math.abs(x.coef));
  const presentOrgans = new Set(present.map((p) => p.organ));
  return {
    cl_id: clId,
    ontology_label: label,
    gene,
    present_in: present,
    absent_in: organs.filter((o) => !presentOrgans.has(o)),
  };
}

// ------------------------------------------------------------------ figures

interface PlotlyFigure {
  data: unknown[];
  layout: Record<string, unknown>;
}

interface Embedding {
  cell_types: string[];
  x: number[];
  y: number[];
  c: number[];
}

/** Layout shared with plots.py::_fig (theme colors are applied by PlotlyChart). */
function umapLayout(title: string, height: number): Record<string, unknown> {
  return {
    title: { text: title },
    margin: { l: 10, r: 10, t: 40, b: 10 },
    font: { size: 12 },
    xaxis: { visible: false },
    yaxis: { visible: false, scaleanchor: "x" },
    height,
  };
}

/** Mirrors plots.py::gene_umap_figure. */
async function geneFigure(slug: string, gene: string): Promise<PlotlyFigure> {
  const [t, emb] = await Promise.all([
    loadExpr(slug),
    staticJSON<Embedding>(`organs/${slug}/embedding.json`),
  ]);
  const want = gene.trim().toUpperCase();
  if (!t || !t.vocab.has(want))
    throw new Error(`404: no gene data for ${slug}`);
  const col = t.geneIndex.get(want);
  const row = new Map(t.labels.map((l, r) => [l, r]));
  const perType = emb.cell_types.map((ct) => {
    const r = row.get(ct);
    return r === undefined ? NaN : meanAt(t, r, col);
  });
  return {
    data: [
      {
        type: "scattergl",
        mode: "markers",
        x: emb.x,
        y: emb.y,
        marker: {
          size: 3,
          color: emb.c.map((c) => perType[c]),
          colorscale: "Viridis",
          colorbar: { title: { text: "mean<br>expr" }, thickness: 12 },
        },
        text: emb.c.map((c) => emb.cell_types[c]),
        hovertemplate: "%{text}<br>expr %{marker.color:.2f}<extra></extra>",
      },
    ],
    layout: umapLayout(`${slug.replace(/_/g, " ")} — ${want} expression`, 520),
  };
}

/** Mirrors plots.py::signature_umap_figure. */
async function signatureFigure(
  slug: string,
  raw: string,
): Promise<PlotlyFigure> {
  const [res, emb] = await Promise.all([
    signatureScores(slug, parseSignatureGenes(raw)),
    staticJSON<Embedding>(`organs/${slug}/embedding.json`),
  ]);
  if (!res || !res.present.length)
    throw new Error(`404: no signature data for ${slug}`);
  const values = emb.c.map((c) => res.scores.get(emb.cell_types[c]) ?? NaN);
  const lim = Math.max(...values.filter(Number.isFinite).map(Math.abs)) || 1;
  return {
    data: [
      {
        type: "scattergl",
        mode: "markers",
        x: emb.x,
        y: emb.y,
        marker: {
          size: 3,
          color: values,
          // plotly.js "RdBu" runs blue -> red, i.e. Python's "RdBu_r".
          colorscale: "RdBu",
          cmid: 0,
          cmin: -lim,
          cmax: lim,
          colorbar: { title: { text: "score" }, thickness: 12 },
        },
        text: emb.c.map((c) => emb.cell_types[c]),
        hovertemplate: "%{text}<br>score %{marker.color:.2f}<extra></extra>",
      },
    ],
    layout: umapLayout(
      `${slug.replace(/_/g, " ")} — signature (${res.present.length} genes)`,
      560,
    ),
  };
}

export type FigureKind = "umap" | "tf" | "cci" | "gsea" | "gene" | "signature";

/** Static counterpart of GET /organs/{slug}/fig/{kind}. */
export function figure(
  slug: string,
  kind: FigureKind,
  opts: { collection?: string; genes?: string } = {},
): Promise<PlotlyFigure> {
  if (kind === "gene") return geneFigure(slug, opts.genes ?? "");
  if (kind === "signature") return signatureFigure(slug, opts.genes ?? "");
  if (kind === "gsea") {
    return staticJSON(
      `organs/${slug}/fig-gsea-${opts.collection ?? "hallmark"}.json`,
    );
  }
  return staticJSON(`organs/${slug}/fig-${kind}.json`);
}
