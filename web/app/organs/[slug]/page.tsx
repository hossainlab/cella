"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  fetchOrgan,
  fetchOrganComposition,
  fetchOrganEmbedding,
  fetchOrganGene,
  fetchOrganCCI,
  fetchOrganGSEA,
  fetchOrganMarkers,
  fetchOrganSignature,
  fetchOrganTF,
} from "@/lib/api";
import type {
  InteractionRow,
  OrganDetail,
  OrganEmbedding,
  OrganGeneExpression,
  OrganMarkerRow,
  PathwayRow,
  SignatureResult,
  StackedComposition,
  TFActivityRow,
} from "@/lib/types";
import Donut from "@/app/components/Donut";
import StackedBar from "@/app/components/StackedBar";
import PlotlyChart from "@/app/components/PlotlyChart";
import { categoryColor } from "@/lib/palette";

type TabKey = "overview" | "gene" | "signature" | "gsea" | "cci" | "tf";

const TABS: { key: TabKey; label: string; available: boolean }[] = [
  { key: "overview", label: "Overview", available: true },
  { key: "gene", label: "Gene expression", available: true },
  { key: "signature", label: "Signature explorer", available: true },
  { key: "tf", label: "TF activity", available: true },
  { key: "gsea", label: "GSEA", available: true },
  { key: "cci", label: "Cell-cell interaction", available: true },
];

export default function OrganDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [organ, setOrgan] = useState<OrganDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");

  useEffect(() => {
    if (slug) fetchOrgan(slug).then(setOrgan).catch((e) => setError(String(e)));
  }, [slug]);

  if (error) return <div className="wrap"><p className="error">Error: {error}</p></div>;
  if (!organ) return <div className="wrap"><p className="muted">Loading…</p></div>;

  return (
    <div className="wrap">
      <p className="crumb">
        <Link href="/organs">← All organs</Link>
      </p>
      <header>
        <h1>{organ.organ}</h1>
        <p className="sub">
          {organ.n_cells.toLocaleString()} cells · {organ.n_cell_types} cell types
          · {organ.n_datasets} datasets · {organ.n_donors} donors
        </p>
      </header>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? "active" : ""} ${t.available ? "" : "disabled"}`}
            onClick={() => t.available && setTab(t.key)}
            disabled={!t.available}
            title={t.available ? undefined : "Requires expression-derived data not in this build"}
          >
            {t.label}
            {!t.available && <span className="soon">n/a</span>}
          </button>
        ))}
      </div>

      {tab === "overview" && <Overview slug={slug} organ={organ} />}
      {tab === "gene" && <GenePanel slug={slug} organ={organ} />}
      {tab === "signature" && <SignaturePanel slug={slug} />}
      {tab === "tf" && <TFPanel slug={slug} />}
      {tab === "gsea" && <GSEAPanel slug={slug} />}
      {tab === "cci" && <CCIPanel slug={slug} />}
    </div>
  );
}

function Overview({ slug, organ }: { slug: string; organ: OrganDetail }) {
  const maxPct = Math.max(...organ.composition.map((c) => c.pct), 1);
  const [emb, setEmb] = useState<OrganEmbedding | null>(null);
  const [markers, setMarkers] = useState<OrganMarkerRow[] | null>(null);
  const [stacked, setStacked] = useState<StackedComposition | null>(null);

  useEffect(() => {
    fetchOrganEmbedding(slug).then(setEmb).catch(() => setEmb(null));
    fetchOrganMarkers(slug, 5).then(setMarkers).catch(() => setMarkers(null));
    fetchOrganComposition(slug, "Dataset").then(setStacked).catch(() => setStacked(null));
  }, [slug]);

  // Consistent color per cell type (same index as the UMAP legend).
  const colorOf = (name: string) => {
    const i = emb ? emb.cell_types.indexOf(name) : -1;
    return i >= 0 ? categoryColor(i) : "var(--muted)";
  };

  // Donut: top 12 types by share + aggregated "Other".
  const TOP = 12;
  const top = organ.composition.slice(0, TOP);
  const otherPct = organ.composition
    .slice(TOP)
    .reduce((s, c) => s + c.pct, 0);
  const donutSlices = [
    ...top.map((c) => ({
      label: c.curated_label,
      value: c.pct,
      color: colorOf(c.curated_label),
    })),
    ...(otherPct > 0
      ? [{ label: "Other", value: otherPct, color: "var(--border)" }]
      : []),
  ];

  return (
    <>
      <h2 className="section-label">Cell embedding (UMAP)</h2>
      <p className="helper mb">
        Each dot is a cell, positioned by transcriptomic similarity and colored by
        cell type. Hover for the cell type; click a legend entry to toggle it; drag
        to zoom. Downsampled to 25,000 cells.
      </p>
      <PlotlyChart url={`/api/organs/${slug}/fig/umap`} />

      <div className="meta-cards">
        {[
          ["cells", organ.n_cells.toLocaleString()],
          ["cell types", organ.n_cell_types],
          ["donors", organ.n_donors],
          ["assays", organ.n_assays],
        ].map(([l, n]) => (
          <div className="meta-card" key={l as string}>
            <span className="meta-n">{n}</span>
            <span className="meta-l">{l}</span>
          </div>
        ))}
      </div>

      <div className="meta-lists">
        <div>
          <h4>Source datasets</h4>
          <ul>{organ.datasets.map((d) => <li key={d}>{d}</li>)}</ul>
        </div>
        <div>
          <h4>Assays</h4>
          <ul>{organ.assays.map((a) => <li key={a}>{a}</li>)}</ul>
        </div>
      </div>

      <h2 className="section-label">Cell-type statistics</h2>
      <p className="helper mb">
        Left: overall cell-type proportions in {organ.organ}. Right: proportion
        within each source dataset — shows how composition varies across studies.
      </p>
      <div className="stats-split">
        <div className="donut-wrap">
          <Donut slices={donutSlices} />
          <div className="donut-legend">
            {donutSlices.map((s) => (
              <span key={s.label} className="donut-leg">
                <span className="umap-swatch" style={{ background: s.color }} />
                {s.label} <span className="muted">{s.value.toFixed(1)}%</span>
              </span>
            ))}
          </div>
        </div>
        {stacked ? (
          <StackedBar comp={stacked} colorOf={colorOf} />
        ) : (
          <div className="detail-placeholder">Loading composition…</div>
        )}
      </div>

      <h2 className="section-label">
        Composition detail<span className="count"> {organ.composition.length}</span>
      </h2>
      <p className="helper mb">
        Badge = how many organs each type appears in (<b>organ-unique</b> vs shared
        across the body).
      </p>
      <div className="comp-list">
        {organ.composition.map((c) => (
          <div className="comp-row" key={c.curated_label}>
            <span className="comp-label">
              <span className="umap-swatch" style={{ background: colorOf(c.curated_label) }} />
              {c.curated_label}
              <span className={`org-badge ${c.n_organs === 1 ? "unique" : "shared"}`}>
                {c.n_organs === 1 ? "organ-unique" : `${c.n_organs} organs`}
              </span>
            </span>
            <span className="comp-bar-wrap">
              <span className="comp-bar" style={{ width: `${(c.pct / maxPct) * 100}%` }} />
              <span className="comp-pct">{c.pct}%</span>
            </span>
          </div>
        ))}
      </div>

      <MarkersTable markers={markers} />
    </>
  );
}

function MarkersTable({ markers }: { markers: OrganMarkerRow[] | null }) {
  const [q, setQ] = useState("");
  if (!markers) return null;
  const rows = q.trim()
    ? markers.filter(
      (m) =>
        m.gene.toLowerCase().includes(q.trim().toLowerCase()) ||
        m.cell_type.toLowerCase().includes(q.trim().toLowerCase()),
    )
    : markers;

  return (
    <>
      <h2 className="section-label">Top discriminative genes per cell type</h2>
      <p className="helper mb">
        The genes that most distinguish each cell type here (CellTypist classifier
        weight), with the fraction of that type&apos;s cells expressing them.
      </p>
      <form className="atlas-search" onSubmit={(e) => e.preventDefault()} role="search">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by gene or cell type…"
          aria-label="Filter markers"
        />
      </form>
      <div className="table-scroll dge-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cell type</th>
              <th>Gene</th>
              <th className="num">Weight</th>
              <th className="num">% expressing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m, i) => (
              <tr key={`${m.cell_type}-${m.gene}-${i}`}>
                <td>{m.cell_type}</td>
                <td className="gene">{m.gene}</td>
                <td className="num">{m.coef.toFixed(2)}</td>
                <td className="num">
                  {m.pct === null ? "—" : `${Math.round(m.pct * 100)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function GenePanel({ slug, organ }: { slug: string; organ: OrganDetail }) {
  const [gene, setGene] = useState("");
  const [data, setData] = useState<OrganGeneExpression | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async (g: string) => {
    if (!g.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      setData(await fetchOrganGene(slug, g.trim()));
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!organ.has_expression) {
    return (
      <div className="detail-placeholder">
        Expression not derived for this organ yet. Run{" "}
        <code>cella derive -o {organ.organ}</code>.
      </div>
    );
  }

  const maxMean = data?.found ? Math.max(...data.rows.map((r) => r.mean), 0.001) : 1;

  return (
    <div className="gene-panel">
      <form
        className="gene-form"
        onSubmit={(e) => {
          e.preventDefault();
          run(gene);
        }}
      >
        <input
          value={gene}
          onChange={(e) => setGene(e.target.value)}
          placeholder="Gene symbol — e.g. MARCO, CD68, EPCAM"
          aria-label="Gene symbol"
        />
        <button type="submit" className="btn">Show</button>
        {["MARCO", "CD68", "EPCAM", "PECAM1"].map((g) => (
          <button
            type="button"
            key={g}
            className="example"
            onClick={() => {
              setGene(g);
              run(g);
            }}
          >
            {g}
          </button>
        ))}
      </form>

      {loading && <p className="muted">Loading…</p>}
      {err && <p className="error">{err}</p>}

      {data && !data.found && (
        <p className="muted note">
          No gene matching “{data.gene}” in {organ.organ}. Try an official symbol.
        </p>
      )}

      {data && data.found && (
        <>
          <p className="helper note">
            <b>{data.gene}</b> expression across {organ.organ}. The UMAP colors each
            cell by its type&apos;s mean expression; below, dot size = fraction of
            cells expressing, color/bar = mean, sorted by mean.
          </p>
          <PlotlyChart
            url={`/api/organs/${slug}/fig/gene?genes=${encodeURIComponent(data.gene)}`}
          />
          <div className="dot-list">
            {data.rows.map((r) => (
              <div className="dot-row" key={r.cell_type}>
                <span className="dot-ct">{r.cell_type}</span>
                <span className="dot-cell">
                  <span
                    className="dot"
                    style={{
                      width: `${6 + r.pct * 18}px`,
                      height: `${6 + r.pct * 18}px`,
                      background: `color-mix(in srgb, var(--accent) ${Math.round(
                        15 + (r.mean / maxMean) * 85,
                      )}%, transparent)`,
                    }}
                    title={`mean ${r.mean.toFixed(2)}, ${Math.round(r.pct * 100)}% expressing`}
                  />
                </span>
                <span className="dot-bar-wrap">
                  <span className="dot-bar" style={{ width: `${(r.mean / maxMean) * 100}%` }} />
                </span>
                <span className="dot-nums">
                  {r.mean.toFixed(2)} · {Math.round(r.pct * 100)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const SIGNATURE_PRESETS: { label: string; genes: string }[] = [
  { label: "Cytotoxic", genes: "GZMB, PRF1, GNLY, NKG7, GZMK" },
  { label: "Interferon", genes: "ISG15, IFI6, MX1, OAS1, IFIT1, IFIT3" },
  { label: "Proliferation", genes: "MKI67, TOP2A, PCNA, CENPF, CCNB1" },
  { label: "Complement (macro)", genes: "C1QA, C1QB, C1QC" },
  { label: "Hypoxia", genes: "VEGFA, CA9, SLC2A1, LDHA" },
];

function SignaturePanel({ slug }: { slug: string }) {
  const [input, setInput] = useState(SIGNATURE_PRESETS[0].genes);
  const [genes, setGenes] = useState(SIGNATURE_PRESETS[0].genes);
  const [res, setRes] = useState<SignatureResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setRes(null);
    setErr(null);
    if (!genes.trim()) return;
    fetchOrganSignature(slug, genes)
      .then(setRes)
      .catch((e) => setErr(String(e)));
  }, [slug, genes]);

  const maxAbs = res ? Math.max(...res.scores.map((s) => Math.abs(s.score)), 1) : 1;

  return (
    <>
      <p className="helper note">
        Score every cell type for a <b>gene signature</b> (module score = mean of
        z-scored expression), then color the UMAP by that score — the{" "}
        <b>Single-Cell Signature Explorer</b> view. Enter genes or pick a preset.
      </p>
      <form
        className="gene-form"
        onSubmit={(e) => {
          e.preventDefault();
          setGenes(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Genes, comma/space separated — e.g. GZMB, PRF1, NKG7"
          aria-label="Signature genes"
        />
        <button type="submit" className="btn">
          Score
        </button>
      </form>
      <div className="examples">
        <span className="helper">Presets:</span>
        {SIGNATURE_PRESETS.map((p) => (
          <button
            key={p.label}
            className="example"
            onClick={() => {
              setInput(p.genes);
              setGenes(p.genes);
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {err && <p className="error">{err}</p>}
      {res && (
        <p className="helper note">
          Matched {res.matched.length} gene{res.matched.length === 1 ? "" : "s"}
          {res.missing.length > 0 && (
            <> · not found: {res.missing.join(", ")}</>
          )}
        </p>
      )}

      {genes.trim() && !err && (
        <PlotlyChart url={`/api/organs/${slug}/fig/signature?genes=${encodeURIComponent(genes)}`} />
      )}

      {res && (
        <div className="table-scroll dge-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Cell type</th>
                <th className="num">Signature score</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              {res.scores.map((s) => (
                <tr key={s.cell_type}>
                  <td>{s.cell_type}</td>
                  <td className="num">{s.score.toFixed(2)}</td>
                  <td>
                    <span className="tf-bar-wrap">
                      <span
                        className="tf-bar"
                        style={{ width: `${(Math.abs(s.score) / maxAbs) * 100}%` }}
                      />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function TFPanel({ slug }: { slug: string }) {
  const [rows, setRows] = useState<TFActivityRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetchOrganTF(slug, 5)
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, [slug]);

  if (err) return <p className="error">{err}</p>;
  if (!rows) return <div className="detail-placeholder">Loading TF activity…</div>;

  const filtered = q.trim()
    ? rows.filter(
      (r) =>
        r.tf.toLowerCase().includes(q.trim().toLowerCase()) ||
        r.cell_type.toLowerCase().includes(q.trim().toLowerCase()),
    )
    : rows;
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.activity)), 1);

  return (
    <>
      <p className="helper note">
        Most cell-type-specific transcription factors per cell type, inferred with{" "}
        <b>decoupler</b> (ULM) over the <b>CollecTRI</b> regulon network on this
        organ&apos;s mean expression. Ranked by activity relative to other cell
        types; bar = activity score.
      </p>
      <PlotlyChart url={`/api/organs/${slug}/fig/tf`} />
      <form className="atlas-search" onSubmit={(e) => e.preventDefault()} role="search">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by TF or cell type…"
          aria-label="Filter transcription factors"
        />
      </form>
      <div className="table-scroll dge-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cell type</th>
              <th>Transcription factor</th>
              <th className="num">Activity</th>
              <th>Relative</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={`${r.cell_type}-${r.tf}-${i}`}>
                <td>{r.cell_type}</td>
                <td className="gene">{r.tf}</td>
                <td className="num">{r.activity.toFixed(1)}</td>
                <td>
                  <span className="tf-bar-wrap">
                    <span
                      className="tf-bar"
                      style={{ width: `${(Math.abs(r.activity) / maxAbs) * 100}%` }}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

const GSEA_COLLECTIONS: { key: string; label: string }[] = [
  { key: "hallmark", label: "Hallmark" },
  { key: "kegg", label: "KEGG" },
  { key: "go_bp", label: "Gene Ontology (BP)" },
  { key: "immunologic", label: "Immunologic signature" },
  { key: "oncogenic", label: "Oncogenic signature" },
  { key: "tft", label: "TF targets" },
];

function GSEAPanel({ slug }: { slug: string }) {
  const [collection, setCollection] = useState("hallmark");
  const [rows, setRows] = useState<PathwayRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    setRows(null);
    setErr(null);
    fetchOrganGSEA(slug, collection, 5)
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, [slug, collection]);

  const filtered = !rows
    ? []
    : q.trim()
      ? rows.filter(
        (r) =>
          r.pathway.toLowerCase().includes(q.trim().toLowerCase()) ||
          r.cell_type.toLowerCase().includes(q.trim().toLowerCase()),
      )
      : rows;
  const maxAbs = Math.max(...(rows ?? []).map((r) => Math.abs(r.score)), 1);

  return (
    <>
      <p className="helper note">
        Most cell-type-specific gene sets per cell type, scored with{" "}
        <b>decoupler</b> (ULM) on this organ&apos;s mean expression over the chosen{" "}
        <b>MSigDB</b> collection. Ranked by activity relative to other cell types.
      </p>
      <div className="collection-bar">
        <span className="helper">Gene-set collection:</span>
        {GSEA_COLLECTIONS.map((c) => (
          <button
            key={c.key}
            className={`example ${collection === c.key ? "on" : ""}`}
            onClick={() => setCollection(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>
      {err && <p className="error">{err}</p>}
      {!rows && !err ? (
        <div className="detail-placeholder">Loading {collection} enrichment…</div>
      ) : (
        <PlotlyChart url={`/api/organs/${slug}/fig/gsea?collection=${collection}`} />
      )}
      <form className="atlas-search" onSubmit={(e) => e.preventDefault()} role="search">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by gene set or cell type…"
          aria-label="Filter gene sets"
        />
      </form>
      <div className="table-scroll dge-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cell type</th>
              <th>Gene set</th>
              <th className="num">Score</th>
              <th>Enrichment</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={`${r.cell_type}-${r.pathway}-${i}`}>
                <td>{r.cell_type}</td>
                <td>{r.pathway}</td>
                <td className="num">{r.score.toFixed(1)}</td>
                <td>
                  <span className="tf-bar-wrap">
                    <span
                      className="tf-bar"
                      style={{ width: `${(Math.abs(r.score) / maxAbs) * 100}%` }}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function CCIPanel({ slug }: { slug: string }) {
  const [rows, setRows] = useState<InteractionRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetchOrganCCI(slug, 150)
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, [slug]);

  if (err) return <p className="error">{err}</p>;
  if (!rows) return <div className="detail-placeholder">Loading interactions…</div>;

  const ql = q.trim().toLowerCase();
  const filtered = ql
    ? rows.filter(
      (r) =>
        r.source.toLowerCase().includes(ql) ||
        r.target.toLowerCase().includes(ql) ||
        r.ligand.toLowerCase().includes(ql) ||
        r.receptor.toLowerCase().includes(ql),
    )
    : rows;
  const maxScore = Math.max(...rows.map((r) => r.score), 1);

  return (
    <>
      <p className="helper note">
        Top ligand-receptor interactions between cell types, scored on mean
        expression (ligand in the <b>source</b> × receptor in the <b>target</b>,
        gated by fraction expressing) over the <b>LIANA</b> consensus resource.
      </p>
      <PlotlyChart url={`/api/organs/${slug}/fig/cci`} />
      <form className="atlas-search" onSubmit={(e) => e.preventDefault()} role="search">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by cell type, ligand, or receptor…"
          aria-label="Filter interactions"
        />
      </form>
      <div className="table-scroll dge-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Source (ligand)</th>
              <th>Target (receptor)</th>
              <th>Interaction</th>
              <th className="num">Score</th>
              <th>Strength</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={`${r.source}-${r.target}-${r.ligand}-${r.receptor}-${i}`}>
                <td>{r.source}</td>
                <td>{r.target}</td>
                <td className="gene">
                  {r.ligand} → {r.receptor}
                </td>
                <td className="num">{r.score.toFixed(1)}</td>
                <td>
                  <span className="tf-bar-wrap">
                    <span
                      className="tf-bar"
                      style={{ width: `${(r.score / maxScore) * 100}%` }}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
