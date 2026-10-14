/**
 * Static-vs-server equivalence check.
 *
 * Runs the browser implementations in lib/static.ts against the files written
 * by `cella export` and compares every answer with the live FastAPI backend.
 * Expression values are quantized in the export (fraction expressing to 1/255,
 * mean to 1/65535 of the organ max), so numbers are compared with tolerances.
 *
 *   uv run --group api uvicorn cella.api.main:app --port 8137 &
 *   uv run --group api cella export --out web/public/data
 *   cd web && npx tsx scripts/check-static.ts [queries.json]
 *
 * queries.json (optional): [{ "term": "...", "genes": "A,B,C" }, ...] for the
 * reverse-lookup comparison; a few built-in signatures are always checked.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";

const API = process.env.API_URL ?? "http://127.0.0.1:8137";
const DATA_DIR = path.resolve(process.env.DATA_DIR ?? "public/data");
const BASE = "/cella"; // exercises the GitHub Pages sub-path handling
process.env.NEXT_PUBLIC_BASE_PATH = BASE;

const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input);
  const prefix = `${BASE}/data/`;
  if (url.startsWith(prefix)) {
    try {
      const body = await readFile(
        path.join(DATA_DIR, decodeURIComponent(url.slice(prefix.length))),
      );
      return new Response(body, { status: 200 });
    } catch {
      return new Response("not found", { status: 404 });
    }
  }
  return realFetch(input, init);
}) as typeof fetch;

const api = async <T>(p: string): Promise<T> => {
  const r = await realFetch(`${API}${p}`);
  if (!r.ok) throw new Error(`${p} -> ${r.status}`);
  return r.json() as Promise<T>;
};

let failures = 0;
const fail = (msg: string) => {
  failures += 1;
  console.log(`  FAIL ${msg}`);
};

interface Hit {
  cl_id: string | null;
  organ: string;
  curated_label: string;
  score: number;
}
interface Lookup {
  hits: Hit[];
  is_confident: boolean;
  matched_genes: string[];
  unknown_genes: string[];
}

async function main() {
  const S = await import("../lib/static");

  // ---- reverse lookup ------------------------------------------------------
  const builtIn = [
    "CD3D,CD3E,CD8A,CD8B,GZMK",
    "MS4A1,CD79A,CD19",
    "MARCO,FABP4,C1QA",
    "ACTB,GAPDH,EEF1A1,TPT1",
    "SFTPC,SFTPB,NAPSA",
    "PECAM1,VWF,CDH5",
  ];
  const file = process.argv[2];
  const extra: { genes: string }[] = file
    ? JSON.parse(await readFile(file, "utf8"))
    : [];
  const queries = [...builtIn, ...extra.map((q) => q.genes)];

  let sameTop = 0;
  let sameConf = 0;
  let tieTop = 0;
  let maxDiff = 0;
  for (const genes of queries) {
    const params = new URLSearchParams({ genes, limit: "15" });
    const [srv, st] = await Promise.all([
      api<Lookup>(`/reverse-lookup?${params}`),
      S.reverseLookup(genes, undefined, 15) as Promise<Lookup>,
    ]);
    if (srv.matched_genes.join() !== st.matched_genes.join()) {
      fail(`matched genes differ for ${genes.slice(0, 40)}`);
      continue;
    }
    if (!srv.hits.length) continue;
    const key = (h: Hit) => `${h.organ}|${h.curated_label}`;
    if (key(srv.hits[0]) === key(st.hits[0])) sameTop += 1;
    else if (Math.abs(srv.hits[0].score - srv.hits[1].score) < 0.004)
      tieTop += 1; // quantization tie
    else
      fail(
        `top hit ${key(srv.hits[0])} vs ${key(st.hits[0])} for ${genes.slice(0, 40)}`,
      );
    if (srv.is_confident === st.is_confident) sameConf += 1;
    const srvScore = new Map(srv.hits.map((h) => [key(h), h.score]));
    for (const h of st.hits) {
      const s = srvScore.get(key(h));
      if (s !== undefined) maxDiff = Math.max(maxDiff, Math.abs(s - h.score));
    }
  }
  const n = queries.length;
  console.log(
    `reverse lookup: ${n} queries; same top hit ${sameTop}, quantization ties ${tieTop}; ` +
      `same confidence ${sameConf}/${n}; max score diff ${maxDiff.toFixed(4)}`,
  );
  if (maxDiff > 0.005) fail(`reverse-lookup score drift ${maxDiff}`);
  // Confidence sits on thresholds; a near-threshold flip from rounding is tolerated once in 50.
  if (n - sameConf > Math.ceil(n / 50))
    fail(`confidence differs in ${n - sameConf}/${n}`);

  // ---- organ gene + signature ---------------------------------------------
  type GeneRows = {
    found: boolean;
    matched_feature: string | null;
    rows: { cell_type: string; mean: number; pct: number }[];
  };
  for (const [slug, gene] of [
    ["Lung", "SFTPC"],
    ["Lung", "c1orf112"],
    ["Blood", "CD3D"],
    ["Hippocampus", "GFAP"],
    ["Liver", "NOTAGENE"],
  ]) {
    const [srv, st] = await Promise.all([
      api<GeneRows>(`/organs/${slug}/gene/${gene}`),
      S.organGene(slug, gene) as Promise<GeneRows>,
    ]);
    if (srv.found !== st.found || srv.matched_feature !== st.matched_feature) {
      fail(
        `organ gene ${slug}/${gene}: found/feature ${srv.matched_feature} vs ${st.matched_feature}`,
      );
      continue;
    }
    const stRow = new Map(st.rows.map((r) => [r.cell_type, r]));
    let dm = 0;
    let dp = 0;
    for (const r of srv.rows) {
      const o = stRow.get(r.cell_type)!;
      dm = Math.max(dm, Math.abs(o.mean - r.mean));
      dp = Math.max(dp, Math.abs(o.pct - r.pct));
    }
    console.log(
      `organ gene ${slug}/${gene}: max |mean| diff ${dm.toFixed(4)}, |pct| diff ${dp.toFixed(4)}`,
    );
    if (dm > 0.002 || dp > 0.003) fail(`organ gene ${slug}/${gene} drift`);
  }

  type Sig = {
    matched: string[];
    missing: string[];
    scores: { cell_type: string; score: number }[];
  };
  for (const [slug, genes] of [
    ["Lung", "SFTPC, SFTPB, NAPSA"],
    ["Blood", "CD3D CD8A GZMK NOTAGENE"],
    ["Kidney", "UMOD,SLC12A1"],
  ]) {
    const [srv, st] = await Promise.all([
      api<Sig>(`/organs/${slug}/signature?genes=${encodeURIComponent(genes)}`),
      S.organSignature(slug, genes) as Promise<Sig>,
    ]);
    const stScore = new Map(st.scores.map((r) => [r.cell_type, r.score]));
    const d = Math.max(
      ...srv.scores.map((r) => Math.abs(r.score - stScore.get(r.cell_type)!)),
    );
    console.log(`signature ${slug}: max score diff ${d.toFixed(4)}`);
    if (
      srv.matched.join() !== st.matched.join() ||
      srv.missing.join() !== st.missing.join()
    ) {
      fail(`signature ${slug}: matched/missing differ`);
    }
    if (d > 0.01) fail(`signature ${slug} drift ${d}`);
  }

  // ---- finite endpoints filtered client-side --------------------------------
  type Graph = {
    nodes: unknown[];
    edges: { source: string; target: string }[];
  };
  for (const organ of [undefined, "Lung"]) {
    const q = new URLSearchParams({ min_similarity: "0.3" });
    if (organ) q.set("organ", organ);
    const [srv, st] = await Promise.all([
      api<Graph>(`/graph?${q}`),
      S.graph(organ, 0.3) as Promise<Graph>,
    ]);
    const ok =
      srv.nodes.length === st.nodes.length &&
      srv.edges.length === st.edges.length;
    console.log(
      `graph ${organ ?? "all"} @0.3: nodes ${st.nodes.length}, edges ${st.edges.length} ${ok ? "ok" : ""}`,
    );
    if (!ok) fail(`graph ${organ ?? "all"} differs`);
  }

  const edges = (await api<Graph>("/graph?min_similarity=0")).edges.slice(0, 5);
  for (const e of edges) {
    for (const [a, b] of [
      [e.source, e.target],
      [e.target, e.source],
    ]) {
      const [srv, st] = await Promise.all([
        api<unknown>(
          `/graph/edge/${encodeURIComponent(a)}/${encodeURIComponent(b)}`,
        ),
        S.edgeDetail(a, b),
      ]);
      if (JSON.stringify(srv) !== JSON.stringify(st))
        fail(`edge detail ${a} -> ${b} differs`);
    }
  }
  console.log(`edge detail: ${edges.length * 2} directed requests compared`);

  for (const [q, min] of [
    ["t cell", 2],
    ["", 1],
    ["CL:00002", 1],
  ] as const) {
    const p = new URLSearchParams({ q, min_organs: String(min), limit: "500" });
    const [srv, st] = await Promise.all([
      api<unknown>(`/cell-types?${p}`),
      S.searchCellTypes(q, min, 500),
    ]);
    if (JSON.stringify(srv) !== JSON.stringify(st))
      fail(`cell-type search "${q}" differs`);
  }
  console.log("cell-type search: 3 queries compared");

  for (const [cl, gene] of [
    ["CL:0000235", "C1QA"],
    ["CL:0000236", "MS4A1"],
    ["CL:0000235", "NOTAGENE"],
  ]) {
    const [srv, st] = await Promise.all([
      api<unknown>(`/fingerprints/${encodeURIComponent(cl)}/gene/${gene}`),
      S.geneAcrossOrgans(cl, gene),
    ]);
    if (JSON.stringify(srv) !== JSON.stringify(st))
      fail(`gene across organs ${cl}/${gene} differs`);
  }
  console.log("gene across organs: 3 queries compared");

  console.log(failures ? `\n${failures} FAILURE(S)` : "\nall checks passed");
  process.exit(failures ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
