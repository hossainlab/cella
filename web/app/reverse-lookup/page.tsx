"use client";

import { useState } from "react";
import { reverseLookup } from "@/lib/api";
import type { ReverseLookup, SignatureHit } from "@/lib/types";

const ORGANS = [
  "Blood", "Bone marrow", "Heart", "Hippocampus", "Intestine", "Kidney",
  "Liver", "Lung", "Lymph node", "Pancreas", "Skeletal muscle", "Spleen",
];

const EXAMPLES = [
  { label: "CD8 T cell", genes: "CD3D, CD3E, CD8A, CD8B, GZMK" },
  { label: "Macrophage", genes: "CD68, C1QA, C1QB, LYZ, MARCO" },
  { label: "B cell", genes: "CD19, MS4A1, CD79A, CD79B" },
  { label: "Fibroblast", genes: "COL1A1, COL1A2, DCN, LUM, PDGFRA" },
];

const POPULAR_GENES = [
  "CD68", "MARCO", "C1QA", "LYZ", "FABP4",
  "CD3D", "CD8A", "CD4", "GZMK", "MS4A1",
  "COL1A1", "PECAM1", "EPCAM", "TREM2"
];

export default function Page() {
  const [genes, setGenes] = useState("");
  const [organ, setOrgan] = useState("");
  const [result, setResult] = useState<ReverseLookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run(g: string, o = organ) {
    if (!g.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await reverseLookup(g, o || undefined, 15));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wrap">
      <header>
        <p className="eyebrow">Zero-Shot Identity Classifier</p>
        <h1 style={{ fontSize: "2.4rem", margin: "0.2rem 0 0.85rem", letterSpacing: "-0.02em" }}>
          Reverse Lookup Classifier
        </h1>
        <p className="sub" style={{ maxWidth: "68ch", fontSize: "1.05rem" }}>
          Paste an experimental gene signature — Cella projects it against every organ model&apos;s{" "}
          <strong>discriminative classifier weights</strong> to rank matching cell types in sub-milliseconds.
        </p>
      </header>

      <details className="callout" style={{ marginBottom: "1.5rem" }}>
        <summary>How the score works</summary>
        <p className="note muted">
          For each cell type, the score is the <b>mean classifier weight</b> of your
          genes — how strongly they <em>distinguish</em> that type in that organ, not
          how highly they&apos;re expressed. Genes outside an organ model&apos;s
          vocabulary are listed as unrecognized. This asks &quot;what do these genes
          define?&quot;, not &quot;where are they on?&quot;.
        </p>
      </details>

      <form
        className="rl-form"
        onSubmit={(e) => {
          e.preventDefault();
          run(genes);
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "0.86rem", fontWeight: 600, color: "var(--muted)" }}>Query Input</span>
          <span style={{ fontSize: "0.78rem", color: "var(--pos)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
            ⚡ &lt;2ms Latency | Processed in Real-Time
          </span>
        </div>

        <textarea
          className="rl-input"
          value={genes}
          onChange={(e) => setGenes(e.target.value)}
          placeholder="Paste genes — comma, space, or newline separated&#10;e.g. CD68, MARCO, C1QA, LYZ, FABP4"
          rows={4}
          aria-label="Gene signature"
        />

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", margin: "0.6rem 0 1rem", alignItems: "center" }}>
          <span className="helper" style={{ marginRight: "0.2rem" }}>Quick add:</span>
          {POPULAR_GENES.map((g) => (
            <button
              key={g}
              type="button"
              className="chip-btn"
              onClick={() => {
                const parts = genes.split(/[\s,]+/).filter(Boolean);
                if (!parts.includes(g)) {
                  parts.push(g);
                  const next = parts.join(", ");
                  setGenes(next);
                }
              }}
            >
              + {g}
            </button>
          ))}
        </div>

        <div className="rl-controls">
          <label>
            Organ Context
            <select value={organ} onChange={(e) => setOrgan(e.target.value)}>
              <option value="">All 12 organs</option>
              {ORGANS.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn-primary" disabled={loading || !genes.trim()}>
            {loading ? "Scoring Manifolds…" : "Analyze Signature →"}
          </button>
        </div>
      </form>

      <div className="examples">
        <span className="helper">Presets:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            className="example"
            onClick={() => {
              setGenes(ex.genes);
              run(ex.genes);
            }}
            title={ex.genes}
          >
            {ex.label}
          </button>
        ))}
      </div>

      {error && <p className="error">Error: {error}</p>}

      {result && <Results result={result} />}
    </div>
  );
}

function Results({ result }: { result: ReverseLookup }) {
  const maxScore = Math.max(...result.hits.map((h) => h.score), 1e-6);
  return (
    <section className="rl-results">
      <div className={`rl-verdict ${result.is_confident ? "ok" : "novel"}`}>
        {result.is_confident ? "✓ Match" : "⚠ No strong match"}
        <span className="rl-note">{result.note}</span>
      </div>

      <div className="rl-genes">
        {result.matched_genes.length > 0 && (
          <div>
            <span className="helper">Recognized ({result.matched_genes.length}):</span>{" "}
            {result.matched_genes.map((g) => (
              <span key={g} className="gene-chip">{g}</span>
            ))}
          </div>
        )}
        {result.unknown_genes.length > 0 && (
          <div className="rl-unknown">
            <span className="helper">Not in any model:</span>{" "}
            {result.unknown_genes.map((g) => (
              <span key={g} className="gene-chip muted-chip">{g}</span>
            ))}
          </div>
        )}
      </div>

      {result.hits.length > 0 && (
        <div className="rl-hits">
          {result.hits.map((h, i) => (
            <HitRow key={`${h.organ}-${h.curated_label}`} hit={h} rank={i + 1} max={maxScore} />
          ))}
        </div>
      )}
    </section>
  );
}

function HitRow({ hit, rank, max }: { hit: SignatureHit; rank: number; max: number }) {
  const pct = Math.max(3, Math.round((hit.score / max) * 100));
  return (
    <div className={`rl-hit ${rank === 1 ? "top" : ""}`}>
      <span className="rl-rank">{rank}</span>
      <div className="rl-hit-body">
        <div className="rl-hit-head">
          <span className="rl-label">{hit.ontology_label}</span>
          <span className="badge">{hit.organ}</span>
          {hit.cl_id && <span className="cl">{hit.cl_id}</span>}
        </div>
        <div className="rl-bar-track">
          <span className="rl-bar" style={{ width: `${pct}%` }} />
          <span className="rl-score">{hit.score.toFixed(3)}</span>
        </div>
        <div className="rl-contrib">
          <span className="helper">defined by:</span>{" "}
          {hit.top_genes
            .filter((g) => g.coef > 0)
            .map((g) => (
              <span key={g.gene} className="gene-chip" title={`weight ${g.coef.toFixed(2)}`}>
                {g.gene}
              </span>
            ))}
        </div>
      </div>
    </div>
  );
}
