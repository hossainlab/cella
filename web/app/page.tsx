import Link from "next/link";

// Deterministic intensity grid for the hero heatmap motif (no client randomness,
// so it renders identically on server and client). Echoes the Marker Atlas view:
// rows = defining genes, columns = organs, brightness = discriminative weight.
const HEAT_COLS = 12;
const HEAT_ROWS = 8;
const heatCells: number[][] = Array.from({ length: HEAT_ROWS }, (_, r) =>
  Array.from({ length: HEAT_COLS }, (_, c) => {
    // A smooth pseudo-pattern: a couple of "universal" bright rows plus scattered
    // organ-specific hotspots, so it reads as a real fingerprint, not noise.
    const universal = r === 1 || r === 4 ? 0.55 : 0;
    const wave = Math.sin(r * 1.7 + c * 0.9) * 0.5 + 0.5;
    const spot = (r * 7 + c * 5) % 11 === 0 ? 0.5 : 0;
    return Math.min(1, universal + wave * 0.5 + spot);
  }),
);

export default function Home() {
  return (
    <div className="wrap">
      <section className="home-hero">
        <div className="hero-copy">
          <p className="eyebrow">Cross-organ cell-type knowledge</p>
          <h1>
            What <em>defines</em> a cell type — and how it changes across the
            body
          </h1>
          <p className="hero-sub">
            A knowledge platform on the CellTypist organ atlases. It surfaces the{" "}
            <strong>discriminative classifier weights</strong> behind cell-type
            annotation — not just which genes are expressed, but which genes{" "}
            <em>distinguish</em> one cell type from another.
          </p>
          <div className="hero-actions">
            <Link href="/marker-atlas" className="btn-primary">
              Open the Marker Atlas →
            </Link>
            <Link href="/graph" className="btn-ghost">
              Explore the graph
            </Link>
            <Link href="/about" className="btn-ghost">
              About →
            </Link>
          </div>
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="heat-card">
            <div
              className="heat-mini"
              style={{ gridTemplateColumns: `repeat(${HEAT_COLS}, 1fr)` }}
            >
              {heatCells.flatMap((row, r) =>
                row.map((v, c) => (
                  <span
                    key={`${r}-${c}`}
                    className="heat-mini-cell"
                    style={{
                      background: `color-mix(in srgb, var(--accent) ${Math.round(
                        8 + v * 88,
                      )}%, transparent)`,
                    }}
                  />
                )),
              )}
            </div>
            <p className="heat-caption">
              Discriminative weights — genes × organs
            </p>
          </div>
        </div>
      </section>

      <section className="stat-band">
        <div className="stat">
          <span className="stat-n">12</span>
          <span className="stat-l">human organs</span>
        </div>
        <div className="stat">
          <span className="stat-n">145</span>
          <span className="stat-l">harmonized cell types</span>
        </div>
        <div className="stat">
          <span className="stat-n">3.6M</span>
          <span className="stat-l">cells (via CellTypist)</span>
        </div>
        <div className="stat">
          <span className="stat-n">5</span>
          <span className="stat-l">interactive tools</span>
        </div>
      </section>

      {/* Tool Showcase Grid */}
      <section className="home-showcase">
        <div className="section-head">
          <div>
            <p className="eyebrow" style={{ marginBottom: "0.4rem" }}>Interactive Toolkit</p>
            <h2>Explore Single-Cell Knowledge</h2>
            <p>From machine learning classifier manifolds to cross-tissue regulatory networks.</p>
          </div>
        </div>

        <div className="home-tools-grid">
          <Link href="/marker-atlas" className="home-tool-card">
            <div className="home-tool-icon-wrap">🎯</div>
            <h3 className="home-tool-title">Discriminative Marker Atlas</h3>
            <p className="home-tool-desc">
              Discover what mathematically defines a cell type. Decompose markers into Universal Core vs. Tissue-Adapted Identity across 12 human organs.
            </p>
            <span className="home-tool-action">Open Atlas →</span>
          </Link>

          <Link href="/organs" className="home-tool-card">
            <div className="home-tool-icon-wrap">🏛️</div>
            <h3 className="home-tool-title">Human Organ Browser</h3>
            <p className="home-tool-desc">
              Browse 12 harmonized organ atlases with 25k UMAP embeddings, cell composition, TF regulons, and cell-cell interactomes.
            </p>
            <span className="home-tool-action">Browse Organs →</span>
          </Link>

          <Link href="/reverse-lookup" className="home-tool-card">
            <div className="home-tool-icon-wrap">⚡</div>
            <h3 className="home-tool-title">Reverse Lookup Classifier</h3>
            <p className="home-tool-desc">
              Paste experimental gene lists to score them against all organ models in &lt;2 ms, deconvolve cell types, and detect novel states.
            </p>
            <span className="home-tool-action">Run Query →</span>
          </Link>

          <Link href="/graph" className="home-tool-card">
            <div className="home-tool-icon-wrap">🕸️</div>
            <h3 className="home-tool-title">Relationship Graph</h3>
            <p className="home-tool-desc">
              Navigate the cross-tissue network of 145 harmonized cell types, explore phenotypic convergence, and inspect shared lineage genes.
            </p>
            <span className="home-tool-action">Explore Graph →</span>
          </Link>

          <Link href="/fingerprint" className="home-tool-card">
            <div className="home-tool-icon-wrap">🔍</div>
            <h3 className="home-tool-title">Fingerprint Explorer</h3>
            <p className="home-tool-desc">
              Side-by-side comparative matrices of positive and negative classifier weights for any cell type across all organs.
            </p>
            <span className="home-tool-action">Compare Fingerprints →</span>
          </Link>

          <Link href="/about" className="home-tool-card">
            <div className="home-tool-icon-wrap">📖</div>
            <h3 className="home-tool-title">About &amp; Research</h3>
            <p className="home-tool-desc">
              Learn the scientific motivation, methodology, and computational contributions behind the Cella platform.
            </p>
            <span className="home-tool-action">Read Overview →</span>
          </Link>
        </div>
      </section>

      <footer className="foot">
        Data: official CellTypist organ atlases &amp; pretrained models. Developed by Md. Jubayer Hossain (DeepBio).{" "}
        <Link href="/about" style={{ color: "var(--accent)" }}>
          Learn more on the About page →
        </Link>
      </footer>
    </div>
  );
}
