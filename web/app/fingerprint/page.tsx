"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchFingerprint,
  fetchGeneAcrossOrgans,
  searchCellTypes,
} from "@/lib/api";
import type {
  CellTypeSummary,
  Fingerprint,
  FingerprintGene,
  GeneAcrossOrgans,
} from "@/lib/types";

const EXAMPLES = [
  { q: "macrophage", note: "tissue-adapted — fingerprint shifts per organ" },
  { q: "fibroblast", note: "stromal, cross-organ" },
  { q: "CD8", note: "conserved — stable fingerprint" },
];

const CAP = 45; // max gene rows in the heatmap

export default function Page() {
  const [allTypes, setAllTypes] = useState<CellTypeSummary[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [fp, setFp] = useState<Fingerprint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const detailRef = useRef<HTMLDivElement>(null);

  const select = useCallback(async (clId: string) => {
    setSelected(clId);
    setLoading(true);
    setError(null);
    setFp(null);
    if (typeof window !== "undefined" && window.innerWidth < 900) {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    try {
      setFp(await fetchFingerprint(clId, 10));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    searchCellTypes("", 2, 500) // need >=2 organs to compare fingerprints
      .then((all) => {
        setAllTypes(all);
        const def = all.find((t) => t.cl_id === "CL:0000235") ?? all[0];
        if (def) select(def.cl_id);
      })
      .catch((e) => setError(String(e)));
  }, [select]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allTypes;
    return allTypes.filter(
      (t) =>
        t.ontology_label.toLowerCase().includes(q) ||
        t.cl_id.toLowerCase().includes(q),
    );
  }, [allTypes, query]);

  return (
    <div className="wrap">
      <header>
        <h1>Cross-Organ Fingerprint Explorer</h1>
        <p className="sub">
          Pick a cell type and compare its{" "}
          <strong>discriminative fingerprint</strong> — the top{" "}
          <span style={{ color: "var(--pos)" }}>up-defining</span> and{" "}
          <span style={{ color: "var(--neg)" }}>down-defining</span> genes — side
          by side across every organ it appears in.
        </p>
      </header>

      <details className="callout">
        <summary>How to read a fingerprint</summary>
        <ul>
          <li>
            Each column is an organ; each row a gene. Color = the gene&apos;s{" "}
            <b>signed classifier weight</b> for this cell type there —{" "}
            <span style={{ color: "var(--pos)" }}>green defines it up</span>,{" "}
            <span style={{ color: "var(--neg)" }}>red defines it down</span>,
            brighter = stronger.
          </li>
          <li>
            A gene bright across a whole row is part of the{" "}
            <b>universal fingerprint</b>; a lone bright cell is{" "}
            <b>tissue-adapted</b>.
          </li>
          <li>
            <b>Click a gene</b> to see its exact weight across every organ.
          </li>
        </ul>
      </details>

      <form
        className="atlas-search"
        onSubmit={(e) => e.preventDefault()}
        role="search"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search cell types — e.g. macrophage, T cell, fibroblast"
          aria-label="Search cell types"
        />
        {query && (
          <button
            type="button"
            className="clear-x"
            aria-label="Clear search"
            onClick={() => setQuery("")}
          >
            ×
          </button>
        )}
      </form>

      <div className="examples">
        <span className="helper">Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.q}
            className="example"
            onClick={() => setQuery(ex.q)}
            title={ex.note}
          >
            {ex.q}
          </button>
        ))}
      </div>

      {error && <p className="error">Error: {error}</p>}

      <div className="split">
        <aside className="pane-list">
          <h2 className="section-label list-head">
            {query ? (
              <>
                Matching “{query.trim()}”
                <span className="count">
                  {" "}
                  {results.length}/{allTypes.length}
                </span>
              </>
            ) : (
              <>
                Cross-organ cell types
                <span className="count"> {allTypes.length}</span>
              </>
            )}
          </h2>
          <div className="results">
            {results.map((r) => (
              <button
                key={r.cl_id}
                className={`result ${selected === r.cl_id ? "active" : ""}`}
                onClick={() => select(r.cl_id)}
              >
                <span className="result-main">
                  <span className="label">{r.ontology_label}</span>
                  <span className="cl">{r.cl_id}</span>
                </span>
                <span className="badge">
                  {r.n_organs} organ{r.n_organs > 1 ? "s" : ""}
                </span>
              </button>
            ))}
            {results.length === 0 && !error && (
              <p className="muted">No cell types match “{query}”.</p>
            )}
          </div>
        </aside>

        <main className="pane-detail" ref={detailRef}>
          {loading ? (
            <div className="detail-placeholder">Loading fingerprint…</div>
          ) : fp ? (
            <FingerprintView fp={fp} />
          ) : (
            <div className="detail-placeholder">
              Select a cell type to see its cross-organ fingerprint.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function cellColor(coef: number, maxAbs: number): string {
  const t = Math.max(0, Math.min(1, Math.abs(coef) / maxAbs));
  const base = coef >= 0 ? "var(--pos)" : "var(--neg)";
  return `color-mix(in srgb, ${base} ${Math.round(12 + t * 88)}%, transparent)`;
}

function FingerprintView({ fp }: { fp: Fingerprint }) {
  const [gene, setGene] = useState<string | null>(null);

  const organs = fp.organs;
  const shown = fp.genes.slice(0, CAP);
  // Global scale across all shown cells so colors are comparable organ-to-organ.
  const maxAbs = useMemo(
    () => Math.max(1e-9, ...shown.flatMap((g) => g.cells.map((c) => Math.abs(c.coef)))),
    [shown],
  );
  // gene -> organ -> cell, for O(1) heatmap lookup.
  const byGene = useMemo(() => {
    const m = new Map<string, Map<string, FingerprintGene["cells"][number]>>();
    for (const g of shown) {
      const row = new Map<string, FingerprintGene["cells"][number]>();
      for (const c of g.cells) row.set(c.organ, c);
      m.set(g.gene, row);
    }
    return m;
  }, [shown]);

  return (
    <section className="atlas">
      <div className="atlas-head">
        <h2>
          {fp.ontology_label} <span className="cl">{fp.cl_id}</span>
        </h2>
        <p className="muted">
          Fingerprint across <strong>{organs.length}</strong> of 12 organs:{" "}
          {organs.join(", ")}
        </p>
      </div>

      <div className="heat-explain">
        <p className="helper note">
          Rows are the genes that most define this cell type; each column an
          organ. <strong>Green = up-defining, red = down-defining</strong>,
          brighter = stronger weight. Rows sorted so shared genes sit on top.
        </p>
        <div className="fp-legend">
          <span>down-defining</span>
          <span className="fp-grad" />
          <span>up-defining</span>
          <span className="muted">· empty = not a top marker in that organ</span>
        </div>
      </div>

      {gene && (
        <GeneDrill clId={fp.cl_id} gene={gene} onClose={() => setGene(null)} />
      )}

      <div className="heat-scroll">
        <div
          className="heat"
          style={{
            gridTemplateColumns: `minmax(96px, 150px) repeat(${organs.length}, minmax(30px, 1fr))`,
          }}
        >
          <div className="heat-corner" />
          {organs.map((o) => (
            <div key={o} className="heat-col" title={o}>
              <span>{o}</span>
            </div>
          ))}

          {shown.map((g) => {
            const row = byGene.get(g.gene)!;
            return (
              <div className="heat-row" key={g.gene} style={{ display: "contents" }}>
                <div
                  className={`heat-gene clickable ${gene === g.gene ? "selected" : ""} ${g.n_organs === organs.length ? "universal" : g.n_organs > 1 ? "shared" : ""}`}
                  title={
                    g.n_organs === 1
                      ? `${g.gene} — organ-specific · click for detail`
                      : `${g.gene} — defines this type in ${g.n_organs}/${organs.length} organs · click for detail`
                  }
                  onClick={() => setGene(gene === g.gene ? null : g.gene)}
                >
                  {g.gene}
                  {g.n_organs > 1 && <span className="heat-count">{g.n_organs}</span>}
                </div>
                {organs.map((o) => {
                  const c = row.get(o);
                  return (
                    <div
                      key={o}
                      className="heat-cell clickable"
                      style={{ background: c ? cellColor(c.coef, maxAbs) : "transparent" }}
                      onClick={() => setGene(g.gene)}
                      title={
                        c
                          ? `${g.gene} in ${o}: ${c.coef >= 0 ? "+" : ""}${c.coef.toFixed(2)} (${c.direction})`
                          : `${g.gene} — not a top marker in ${o}`
                      }
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {fp.genes.length > CAP && (
        <p className="helper note">
          Showing the top {CAP} of {fp.genes.length} defining genes.
        </p>
      )}
    </section>
  );
}

function GeneDrill({
  clId,
  gene,
  onClose,
}: {
  clId: string;
  gene: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<GeneAcrossOrgans | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    fetchGeneAcrossOrgans(clId, gene)
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [clId, gene]);

  const maxAbs = data
    ? Math.max(1e-9, ...data.present_in.map((w) => Math.abs(w.coef)))
    : 1;

  return (
    <div className="fp-drill">
      <div className="fp-drill-head">
        <h3>
          <code>{gene}</code> across organs
        </h3>
        <button className="fp-close" onClick={onClose} aria-label="Close">
          × close
        </button>
      </div>

      {err && <p className="error">Error: {err}</p>}
      {!data && !err && <p className="muted">Loading…</p>}

      {data &&
        data.present_in.map((w) => {
          const t = Math.min(1, Math.abs(w.coef) / maxAbs);
          const half = (t * 50).toFixed(1); // % of the track's half-width
          const pos = w.coef >= 0;
          return (
            <div className="fp-bar-row" key={w.organ}>
              <span className="fp-bar-organ" title={w.organ}>
                {w.organ}
              </span>
              <span className="fp-bar-track">
                <span className="fp-bar-mid" />
                <span
                  className="fp-bar"
                  style={{
                    background: pos ? "var(--pos)" : "var(--neg)",
                    left: pos ? "50%" : `calc(50% - ${half}%)`,
                    width: `${half}%`,
                  }}
                />
              </span>
              <span className="fp-bar-val">
                {pos ? "+" : ""}
                {w.coef.toFixed(3)}
              </span>
            </div>
          );
        })}

      {data && data.present_in.length === 0 && (
        <p className="muted">
          Not a top discriminative gene in any organ for this cell type.
        </p>
      )}

      {data && data.absent_in.length > 0 && (
        <p className="fp-absent muted">
          Not among the stored top markers in: {data.absent_in.join(", ")}.
        </p>
      )}
    </div>
  );
}
