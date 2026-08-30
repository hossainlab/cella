"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchMarkerAtlas, searchCellTypes } from "@/lib/api";
import type { CellTypeSummary, MarkerAtlas } from "@/lib/types";

const EXAMPLES = [
  { q: "macrophage", note: "tissue-adapted — no universal genes" },
  { q: "CD8", note: "conserved — shared genes everywhere" },
  { q: "fibroblast", note: "stromal, cross-organ" },
  { q: "endothelial", note: "vascular lineage" },
  { q: "B cell", note: "humoral immunity" },
  { q: "monocyte", note: "circulating myeloid" },
];

export default function Page() {
  const [allTypes, setAllTypes] = useState<CellTypeSummary[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [atlas, setAtlas] = useState<MarkerAtlas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const detailRef = useRef<HTMLDivElement>(null);

  const select = useCallback(async (clId: string) => {
    setSelected(clId);
    setLoading(true);
    setError(null);
    setAtlas(null);
    // On stacked (mobile) layout the detail is below the list — bring it into view.
    if (typeof window !== "undefined" && window.innerWidth < 900) {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    try {
      setAtlas(await fetchMarkerAtlas(clId, 10));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Load the full catalog once; the search box filters it client-side.
  useEffect(() => {
    searchCellTypes("", 1, 500)
      .then((all) => {
        setAllTypes(all);
        const def = all.find((t) => t.cl_id === "CL:0000235") ?? all[0];
        if (def) select(def.cl_id); // land on a populated heatmap (macrophage)
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
        <p className="eyebrow">Discriminative Feature Space</p>
        <h1 style={{ fontSize: "2.4rem", margin: "0.2rem 0 0.85rem", letterSpacing: "-0.02em" }}>
          Discriminative Marker Atlas
        </h1>
        <p className="sub" style={{ maxWidth: "68ch", fontSize: "1.05rem" }}>
          Pick a cell type to discover <strong>which genes define its identity</strong> — and
          how that definition shifts across 12 human organs. Built on CellTypist regularized ML classifier weights.
        </p>
      </header>

      <details className="callout">
        <summary>How to read this atlas</summary>
        <ul>
          <li>
            A <b>discriminative gene</b> is one that <em>distinguishes</em> this
            cell type from the others in the same organ — not just a gene that
            happens to be switched on.
          </li>
          <li>
            <b>Shared / universal identity</b> = genes that define the cell type
            in many organs — bright across a whole row of the heatmap.
          </li>
          <li>
            <b>Tissue-adapted identity</b> = genes that define it in only one
            organ — a single bright cell in a row.
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
                All cell types
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
            <div className="detail-placeholder">Loading marker atlas…</div>
          ) : atlas ? (
            <Atlas atlas={atlas} />
          ) : (
            <div className="detail-placeholder">
              Select a cell type from the list to see its marker atlas.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function buildMatrix(atlas: MarkerAtlas) {
  // gene -> organ -> coef, from each organ's positive markers.
  const byGene = new Map<string, Map<string, number>>();
  for (const om of atlas.per_organ) {
    for (const g of om.positive) {
      if (!byGene.has(g.gene)) byGene.set(g.gene, new Map());
      const prev = byGene.get(g.gene)!.get(om.organ);
      // keep the strongest weight if a gene appears via multiple curated labels
      if (prev === undefined || g.coef > prev) byGene.get(g.gene)!.set(om.organ, g.coef);
    }
  }
  let maxCoef = 0;
  for (const organs of byGene.values())
    for (const c of organs.values()) maxCoef = Math.max(maxCoef, c);

  const genes = [...byGene.entries()]
    .map(([gene, organs]) => ({
      gene,
      organs,
      nOrgans: organs.size,
      maxG: Math.max(...organs.values()),
    }))
    .sort((a, b) => b.nOrgans - a.nOrgans || b.maxG - a.maxG);

  return { genes, maxCoef: maxCoef || 1 };
}

function cellColor(coef: number | undefined, maxCoef: number): string {
  if (coef === undefined) return "transparent";
  const t = Math.max(0, Math.min(1, coef / maxCoef));
  // low -> faint, high -> solid accent
  return `color-mix(in srgb, var(--accent) ${Math.round(12 + t * 88)}%, transparent)`;
}

function Atlas({ atlas }: { atlas: MarkerAtlas }) {
  const single = atlas.organs.length === 1;
  const { genes, maxCoef } = buildMatrix(atlas);
  const CAP = 45;
  const shown = genes.slice(0, CAP);
  const organs = atlas.organs;

  return (
    <section className="atlas">
      <div className="atlas-head">
        <h2>
          {atlas.ontology_label} <span className="cl">{atlas.cl_id}</span>
        </h2>
        <p className="muted">
          Found in <strong>{organs.length}</strong> of 12 organs:{" "}
          {organs.join(", ")}
        </p>
      </div>

      {single ? (
        <p className="muted note">
          This cell type appears in only one organ, so there is nothing to
          compare across tissues.
        </p>
      ) : (
        <>
          <div className="heat-explain">
            <p className="helper note">
              Each row is a defining gene; each column an organ. A filled cell
              means the gene is a top marker of this cell type in that organ —{" "}
              <strong>brighter = defines it more strongly</strong>. Rows are
              sorted so <strong>shared genes (bright across many columns)</strong>{" "}
              sit at the top and <strong>organ-specific genes</strong> (a single
              bright cell) at the bottom.
            </p>
            <div className="heat-legend">
              <span className="hl-scale">
                weak
                <span className="hl-grad" />
                strong
              </span>
              <span className="muted">
                empty = not a top marker in that organ
              </span>
            </div>
          </div>

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

              {shown.map(({ gene, organs: g, nOrgans }) => (
                <div className="heat-row" key={gene} style={{ display: "contents" }}>
                  <div
                    className={`heat-gene ${nOrgans === organs.length ? "universal" : nOrgans > 1 ? "shared" : ""}`}
                    title={
                      nOrgans === 1
                        ? `${gene} — organ-specific`
                        : `${gene} — defines this type in ${nOrgans}/${organs.length} organs`
                    }
                  >
                    {gene}
                    {nOrgans > 1 && (
                      <span className="heat-count">{nOrgans}</span>
                    )}
                  </div>
                  {organs.map((o) => {
                    const coef = g.get(o);
                    return (
                      <div
                        key={o}
                        className="heat-cell"
                        style={{ background: cellColor(coef, maxCoef) }}
                        title={
                          coef === undefined
                            ? `${gene} — not a top marker in ${o}`
                            : `${gene} in ${o}: weight ${coef.toFixed(2)}`
                        }
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>

          {genes.length > CAP && (
            <p className="helper note">
              Showing the top {CAP} of {genes.length} defining genes.
            </p>
          )}
        </>
      )}
    </section>
  );
}
