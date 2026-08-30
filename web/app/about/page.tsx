import Link from "next/link";

export const metadata = {
  title: "About — Cella",
  description:
    "Scientific rationale, computational methodologies, and key contributions behind Cella — an interpretable knowledge platform over human single-cell organ atlases.",
};

export default function AboutPage() {
  return (
    <div className="wrap">
      {/* Header */}
      <section className="about-hero">
        <p className="eyebrow">About Cella</p>
        <h1 className="about-title">
          Decoding Cell-Type Identity Beyond Raw Expression
        </h1>
        <p className="about-lead">
          <strong>Cella</strong> (Latin for <em>cell</em>) is an open-source biological
          knowledge and decision-support platform built on the{" "}
          <strong>CellTypist Human Organ Atlases</strong>. It transforms machine learning
          classifier weights and cross-organ cellular networks into an interactive,
          interpretable knowledge engine.
        </p>

        <div className="about-tags">
          <span className="about-tag">🧬 12 Human Organs</span>
          <span className="about-tag">🔬 &gt;3.6 Million Cells</span>
          <span className="about-tag">🏷️ 145 Harmonized Cell Types</span>
          <span className="about-tag">⚡ Machine Learning Weights</span>
          <span className="about-tag">🌐 Open Source &amp; Reproducible</span>
        </div>
      </section>

      {/* The Core Biological Problem */}
      <section className="about-section">
        <h2 className="about-h2">1. The Scientific Problem: Expression vs. Discriminative Identity</h2>
        <p>
          Single-cell RNA sequencing (scRNA-seq) has mapped millions of human cells across
          diverse organs. However, almost all existing atlas browsers (such as CELLxGENE or
          the Broad Single Cell Portal) only answer one fundamental question:
        </p>
        <div className="quote-box">
          <em>&ldquo;Is gene X detected in cell type Y?&rdquo;</em> (Expression-based view)
        </div>
        <p>
          While informative, raw gene expression is often <strong>noisy</strong>, plagued by{" "}
          <strong>technical dropouts</strong>, and dominated by ubiquitous metabolic or
          housekeeping genes that do not define what makes a cell type unique.
        </p>
        <p>
          When machine learning models (such as CellTypist&apos;s regularized logistic regression
          classifiers) are trained to annotate cells, they learn <strong>discriminative classifier weights</strong> (
          <code className="code-inline">&beta; coefficients</code>). These weights explicitly answer a far
          deeper biological question:
        </p>
        <div className="quote-box highlight">
          <em>
            &ldquo;Which genes <strong>distinguish</strong> cell type Y from every other cell
            type in this tissue, and how does that definition shift across the human body?&rdquo;
          </em>
        </div>
        <p>
          Until Cella, these classifier weights remained trapped inside serialized Python{" "}
          <code className="code-inline">.pkl</code> model files and static journal figures. Cella extracts,
          harmonizes, and surfaces these weights as an interactive suite of analytical tools.
        </p>
      </section>

      {/* Comparison Table */}
      <section className="about-section">
        <h3 className="about-h3">Traditional Atlas Viewers vs. Cella</h3>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Feature / Dimension</th>
                <th>Traditional Atlas Portals</th>
                <th>Cella Platform</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Primary Data Asset</strong></td>
                <td>Raw / normalized expression matrices (X)</td>
                <td>Learned discriminative weight matrices (W) + Cell Ontology graph</td>
              </tr>
              <tr>
                <td><strong>Marker Identification</strong></td>
                <td>Heuristic differential expression or curated lists</td>
                <td>Regularized logistic regression classifier coefficients</td>
              </tr>
              <tr>
                <td><strong>Cross-Organ Comparison</strong></td>
                <td>Manual inspection of disjoint tissue datasets</td>
                <td>Systematic split into <em>Universal Core</em> vs. <em>Tissue-Adapted</em> markers</td>
              </tr>
              <tr>
                <td><strong>Reverse Querying</strong></td>
                <td>Basic gene search across expression tables</td>
                <td>Zero-shot signature scoring against multi-organ ML weight vectors</td>
              </tr>
              <tr>
                <td><strong>Cross-Tissue Relationships</strong></td>
                <td>Static dendrograms or single-tissue UMAPs</td>
                <td>Interactive ~145-node cross-organ similarity &amp; lineage graph</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Key Research Contributions (PhD Committee Focus) */}
      <section className="about-section">
        <h2 className="about-h2">2. Key Research &amp; Methodological Contributions</h2>
        <p className="muted mb">
          This project represents an original integration of computational biology, machine learning
          interpretability, and scalable software systems engineering. Below are the primary
          methodological contributions:
        </p>

        <div className="contrib-grid">
          {/* Contribution 1 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge theory">Theoretical &amp; Biological</span>
              <h3 className="contrib-title">Universal Core vs. Tissue-Adapted Identity</h3>
            </div>
            <p className="contrib-desc">
              Formulated a systematic framework to decompose cellular identity across organs.
              By evaluating discriminative weights across all 12 organs where a cell type resides,
              Cella partitions markers into:
            </p>
            <ul className="contrib-list">
              <li>
                <strong>Universal Core Identity:</strong> Consensus genes with high positive weights (
                <code className="code-inline">&beta; &gt; 0</code>) in every organ (e.g., canonical lineage
                regulators like <em>CD3D/E</em> for T cells).
              </li>
              <li>
                <strong>Tissue-Adapted Identity:</strong> Genes with strong discriminative power only in a
                single organ, capturing microenvironmental adaptations (e.g., <em>MARCO</em> in alveolar
                macrophages vs. <em>C1QA/B</em> in microglia).
              </li>
            </ul>
          </div>

          {/* Contribution 2 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge ontology">Ontology &amp; Harmonization</span>
              <h3 className="contrib-title">Cell Ontology (CL) Graph Alignment</h3>
            </div>
            <p className="contrib-desc">
              Heterogeneous dataset annotations across 38 studies were mapped and standardized into a
              unified Cell Ontology directed acyclic graph (CL IDs). This provides a single join key
              across 145 canonical cell types, resolving synonymy and inconsistent nomenclature across
              differing lab annotations.
            </p>
          </div>

          {/* Contribution 3 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge graph">Network Biology</span>
              <h3 className="contrib-title">Cross-Tissue Relationship &amp; Lineage Graph</h3>
            </div>
            <p className="contrib-desc">
              Constructed an interactive cross-organ cell-type relationship graph based on cosine similarity
              between high-dimensional classifier weight vectors. Precomputed deterministic spring embeddings
              enable researchers to explore phenotypic convergence, developmental lineages, and shared
              regulatory programs across the human body without client-side simulation lag.
            </p>
          </div>

          {/* Contribution 4 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge ml">Algorithms &amp; ML</span>
              <h3 className="contrib-title">Instant Reverse-Lookup Signature Classifier</h3>
            </div>
            <p className="contrib-desc">
              Designed a fast reverse-lookup engine that projects user-provided gene signatures
              against 12 organ model weight matrices in sub-milliseconds (&lt; 2 ms). It provides:
            </p>
            <ul className="contrib-list">
              <li>Quantitative confidence scoring based on discriminative weight strength.</li>
              <li>Deconvolution of which organ/tissue best matches the query signature.</li>
              <li>Automated flagging of potential novel, rare, or uncharacterized cellular states.</li>
            </ul>
          </div>

          {/* Contribution 5 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge multiomics">Multi-Omics Inference</span>
              <h3 className="contrib-title">Downstream Functional &amp; Regulatory Derivations</h3>
            </div>
            <p className="contrib-desc">
              Integrated multi-modal analytical layers on top of atlas pseudobulk profiles:
            </p>
            <ul className="contrib-list">
              <li><strong>Transcription Factor Activity:</strong> Univariate Linear Modeling (ULM) over CollecTRI regulons via Decoupler.</li>
              <li><strong>Pathway Activity:</strong> GSEA Hallmark enrichment per cell type.</li>
              <li><strong>Cell-Cell Communication:</strong> Ligand-receptor interactome reconstruction using LIANA consensus databases.</li>
            </ul>
          </div>

          {/* Contribution 6 */}
          <div className="contrib-card">
            <div className="contrib-header">
              <span className="contrib-badge systems">Systems Engineering</span>
              <h3 className="contrib-title">Zero-Overhead Data Pipeline &amp; 60 FPS UI</h3>
            </div>
            <p className="contrib-desc">
              Built an efficient, reproducible computational pipeline and high-performance web interface:
            </p>
            <ul className="contrib-list">
              <li><strong>Remote HDF5 Range Reads:</strong> Extracts cell metadata from remote Sanger buckets in seconds via HTTP range requests without downloading 30+ GB raw files.</li>
              <li><strong>Vectorized In-Memory Serving:</strong> FastAPI backend with Parquet columnar caches, sub-millisecond query responses, and ETag cache revalidation.</li>
              <li><strong>Batched Canvas Rendering:</strong> Custom HTML5 Canvas rendering engine for 25,000 cells running at a locked 60 FPS.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Platform Tools Summary */}
      <section className="about-section">
        <h2 className="about-h2">3. The 5 Interactive Tools</h2>
        <div className="tools-cards">
          <Link href="/organs" className="tool-card-link">
            <div className="tool-card">
              <span className="tool-icon">🏛️</span>
              <div>
                <h4 className="tool-title">Organ Browser</h4>
                <p className="tool-desc">
                  Explore 12 organ atlases — donor demographics, cell composition, 25k UMAP embeddings,
                  TF activity, and cell-cell communication networks.
                </p>
              </div>
            </div>
          </Link>

          <Link href="/marker-atlas" className="tool-card-link">
            <div className="tool-card">
              <span className="tool-icon">🎯</span>
              <div>
                <h4 className="tool-title">Discriminative Marker Atlas</h4>
                <p className="tool-desc">
                  Query any cell type to inspect its universal core defining genes versus tissue-adapted
                  organ-specific markers.
                </p>
              </div>
            </div>
          </Link>

          <Link href="/fingerprint" className="tool-card-link">
            <div className="tool-card">
              <span className="tool-icon">🔍</span>
              <div>
                <h4 className="tool-title">Fingerprint Explorer</h4>
                <p className="tool-desc">
                  Compare side-by-side heatmaps of positive and negative classifier weights for the same cell
                  type across different organs.
                </p>
              </div>
            </div>
          </Link>

          <Link href="/graph" className="tool-card-link">
            <div className="tool-card">
              <span className="tool-icon">🕸️</span>
              <div>
                <h4 className="tool-title">Relationship Graph</h4>
                <p className="tool-desc">
                  Navigate the cross-tissue network of 145 harmonized cell types, filtering by organ and
                  inspecting shared discriminative features.
                </p>
              </div>
            </div>
          </Link>

          <Link href="/reverse-lookup" className="tool-card-link">
            <div className="tool-card">
              <span className="tool-icon">⚡</span>
              <div>
                <h4 className="tool-title">Reverse Lookup</h4>
                <p className="tool-desc">
                  Paste experimental gene lists to score them against all organ models, identify candidate cell
                  types, and detect novel states.
                </p>
              </div>
            </div>
          </Link>
        </div>
      </section>

      {/* Research Profile & Scientific Roadmap */}
      <section className="about-section">
        <h2 className="about-h2">4. Research Profile &amp; Scientific Roadmap</h2>
        <div className="researcher-card">
          <div className="researcher-header">
            <div>
              <h3 className="researcher-name">Md. Jubayer Hossain</h3>
              <p className="researcher-subtitle">
                Founder &amp; CEO, DeepBio · Multi-Omics Scientist
              </p>
            </div>
          </div>
          <p className="researcher-bio">
            This project was conceived, architected, and developed by <strong>Md. Jubayer Hossain</strong> as an
            independent research initiative bridging <strong>large-scale single-cell transcriptomics</strong>,{" "}
            <strong>interpretable machine learning</strong>, and <strong>high-performance bioinformatics software engineering</strong>.
          </p>
          <h4 className="about-h4">Future Research &amp; Roadmap:</h4>
          <ul className="vision-list">
            <li>
              <strong>Spatial Transcriptomics Integration:</strong> Mapping discriminative classifier
              weights onto 10x Visium and CosMx spatial coordinates to study in situ cellular niches and
              neighborhood interactions.
            </li>
            <li>
              <strong>Single-Cell Foundation Model Embeddings:</strong> Comparing linear discriminative
              weight manifolds against latent representations from generative foundation models (e.g., scGPT,
              Geneformer, scVI).
            </li>
            <li>
              <strong>Disease State Perturbation Modeling:</strong> Extending the cross-organ framework to
              characterize pathological shifts in cell identity during autoimmune conditions, chronic inflammation,
              and cancer metastasis.
            </li>
          </ul>
        </div>
      </section>

      {/* Citations and Data Sources */}
      <section className="about-section">
        <h2 className="about-h2">5. Data Sources &amp; Citations</h2>
        <p className="muted">
          All biological data utilized in Cella is sourced from official, peer-reviewed reference resources:
        </p>
        <div className="citation-box">
          <p>
            <strong>CellTypist Organ Atlases &amp; Models:</strong><br />
            Domínguez Conde, C., Xu, C., Jarvis, L. B., Rainbow, D. B., et al. (2022).{" "}
            <em>Cross-tissue immune cell analysis reveals tissue-specific features in humans.</em>{" "}
            <strong>Science</strong>, 376(6594), eabl5197.{" "}
            <a
              href="https://doi.org/10.1126/science.abl5197"
              target="_blank"
              rel="noopener noreferrer"
              className="about-link"
            >
              doi:10.1126/science.abl5197
            </a>
          </p>
          <p>
            <strong>CellTypist v2 Reference:</strong><br />
            Xu, C., et al. (2024).{" "}
            <em>CellTypist 2.0: A comprehensive reference atlas for automated cell-type annotation across human organs.</em>{" "}
            <a
              href="https://www.celltypist.org"
              target="_blank"
              rel="noopener noreferrer"
              className="about-link"
            >
              celltypist.org
            </a>
          </p>
          <p>
            <strong>Cell Ontology (CL):</strong><br />
            Diehl, A. D., et al. (2016).{" "}
            <em>The Cell Ontology 2016: enhanced content, modularization, and ontology interoperability.</em>{" "}
            <strong>Journal of Biomedical Semantics</strong>, 7(1), 44.
          </p>
        </div>
      </section>
    </div>
  );
}

