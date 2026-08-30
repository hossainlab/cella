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
        <h1>Reverse Lookup</h1>
        <p className="sub">
          The inverse of the Marker Atlas. Paste a gene signature — Cella scores
          it against every organ model&apos;s <strong>discriminative weights</strong>{" "}
          and ranks the cell types it most <em>defines</em>. A weak match flags a
          possible novel or uncharacterized state.
        </p>
      </header>

      <details className="callout">
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
        <textarea
          className="rl-input"
          value={genes}
          onChange={(e) => setGenes(e.target.value)}
          placeholder="Paste genes — comma, space, or newline separated&#10;e.g. CD3D CD8A GZMK"
          rows={4}
          aria-label="Gene signature"
        />
        <div className="rl-controls">
          <label>
            Organ
            <select value={organ} onChange={(e) => setOrgan(e.target.value)}>
              <option value="">All 12 organs</option>
              {ORGANS.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn-primary" disabled={loading || !genes.trim()}>
            {loading ? "Scoring…" : "Identify cell type →"}
          </button>
        </div>
      </form>

      <div className="examples">
        <span className="helper">Try:</span>
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
