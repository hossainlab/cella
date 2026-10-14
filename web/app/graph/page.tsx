"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchEdgeDetail, fetchGraph } from "@/lib/api";
import type {
  EdgeDetail,
  GraphEdge,
  GraphNode,
  RelationshipGraph,
} from "@/lib/types";
import { categoryColor } from "@/lib/palette";
import { cssVar, useResolvedTheme } from "@/lib/theme";

export default function Page() {
  const [organ, setOrgan] = useState<string>("");
  const [minSim, setMinSim] = useState(0.3);
  const [graph, setGraph] = useState<RelationshipGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchGraph(organ || undefined, minSim)
      .then((g) => {
        setGraph(g);
        setSelected(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [organ, minSim]);

  const organColor = useMemo(() => {
    const m = new Map<string, string>();
    graph?.organs.forEach((o, i) => m.set(o, categoryColor(i)));
    return m;
  }, [graph]);

  return (
    <div className="wrap">
      <header>
        <h1>Relationship Graph Explorer</h1>
        <p className="sub">
          How do the <strong>145 harmonized cell types</strong> across 12 organs
          relate? Each node is a cell type, sized by cell count and colored by
          organ; each link is <strong>transcriptomic similarity</strong> between
          their classifier fingerprints.
        </p>
      </header>

      <details className="callout">
        <summary>How this graph is built</summary>
        <p className="note muted">
          v1 uses the documented <b>similarity-graph approximation</b>: edges
          are the cosine similarity between cell types&apos; classifier-weight
          vectors (not the CellTypist v2.0 predictive-clustering tree, which is
          future work). A link means two types have{" "}
          <b>similar discriminative fingerprints</b> — often lineage relatives.
          Click a node to see its nearest relatives; click a relative to see the
          genes they share.
        </p>
      </details>

      <div className="graph-controls">
        <label>
          Organ
          <select value={organ} onChange={(e) => setOrgan(e.target.value)}>
            <option value="">All 12 organs</option>
            {graph?.organs.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label className="slider">
          Min similarity <span className="mono">{minSim.toFixed(2)}</span>
          <input
            type="range"
            min={0}
            max={0.9}
            step={0.05}
            value={minSim}
            onChange={(e) => setMinSim(Number(e.target.value))}
          />
        </label>
        <label className="grow">
          Find
          <input
            type="text"
            placeholder="Highlight a cell type — e.g. macrophage"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>

      {error && <p className="error">Error: {error}</p>}

      <div className="graph-split">
        <div className="graph-canvas-wrap">
          {loading && (
            <div className="detail-placeholder">
              Loading relationship graph…
            </div>
          )}
          {graph && (
            <>
              <GraphCanvas
                graph={graph}
                organColor={organColor}
                selected={selected}
                search={search}
                onSelect={setSelected}
              />
              <p className="helper note">
                Showing {graph.nodes.length} of {graph.n_total_nodes} cell types
                {organ ? ` in ${organ}` : ""} · {graph.edges.length} links.
                Scroll to zoom, drag to pan.
              </p>
            </>
          )}
        </div>

        <aside className="graph-side">
          {selected ? (
            <NodePanel
              node={selected}
              graph={graph!}
              organColor={organColor}
              onPick={setSelected}
            />
          ) : (
            <div className="detail-placeholder">
              Click a node to inspect a cell type and its nearest relatives.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

type PlotlyModule = typeof import("plotly.js-dist-min");

function GraphCanvas({
  graph,
  organColor,
  selected,
  search,
  onSelect,
}: {
  graph: RelationshipGraph;
  organColor: Map<string, string>;
  selected: GraphNode | null;
  search: string;
  onSelect: (n: GraphNode) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const plotlyRef = useRef<PlotlyModule["default"] | null>(null);
  const theme = useResolvedTheme();
  const nodeById = useMemo(
    () => new Map(graph.nodes.map((n) => [n.cl_id, n])),
    [graph],
  );

  // Latest node map + select callback, read by the single persistent click
  // listener so it never needs re-attaching across redraws.
  const clickRef = useRef<(clId: string) => void>(() => {});
  clickRef.current = (clId: string) => {
    const n = nodeById.get(clId);
    if (n) onSelect(n);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const mod = await import("plotly.js-dist-min");
      if (cancelled || !ref.current) return;
      const Plotly = mod.default;
      plotlyRef.current = Plotly;

      const maxCells = Math.max(...graph.nodes.map((n) => n.total_cells), 1);
      const selId = selected?.cl_id ?? null;
      const q = search.trim().toLowerCase();
      // Neighbors of the selected node, to keep edges/nodes bright.
      const near = new Set<string>();
      if (selId) {
        near.add(selId);
        for (const e of graph.edges) {
          if (e.source === selId) near.add(e.target);
          if (e.target === selId) near.add(e.source);
        }
      }

      // Edge segments: bright if incident to the selected node, else faint.
      const ex: (number | null)[] = [];
      const ey: (number | null)[] = [];
      const hx: (number | null)[] = [];
      const hy: (number | null)[] = [];
      for (const e of graph.edges) {
        const a = nodeById.get(e.source);
        const b = nodeById.get(e.target);
        if (!a || !b) continue;
        const hot = selId && (e.source === selId || e.target === selId);
        const xs = hot ? hx : ex;
        const ys = hot ? hy : ey;
        xs.push(a.x, b.x, null);
        ys.push(a.y, b.y, null);
      }

      const edgeTrace = {
        x: ex,
        y: ey,
        mode: "lines",
        type: "scattergl",
        line: { color: cssVar("--plot-edge"), width: 1 },
        hoverinfo: "none",
        showlegend: false,
      };
      const hotEdgeTrace = {
        x: hx,
        y: hy,
        mode: "lines",
        type: "scattergl",
        line: { color: cssVar("--plot-edge-hot"), width: 1.5 },
        hoverinfo: "none",
        showlegend: false,
      };

      // One marker trace per organ so the legend is an organ key.
      const nodeTraces = graph.organs
        .map((o) => {
          const ns = graph.nodes.filter((n) => n.primary_organ === o);
          if (!ns.length) return null;
          return {
            x: ns.map((n) => n.x),
            y: ns.map((n) => n.y),
            customdata: ns.map((n) => n.cl_id),
            text: ns.map((n) => n.label),
            name: o,
            mode: "markers",
            type: "scattergl",
            hovertemplate: `<b>%{text}</b><br>${o}<extra></extra>`,
            marker: {
              size: ns.map((n) => 7 + 26 * Math.sqrt(n.total_cells / maxCells)),
              color: organColor.get(o),
              opacity: ns.map((n) => {
                if (q && !n.label.toLowerCase().includes(q)) return 0.15;
                if (selId && !near.has(n.cl_id)) return 0.2;
                return 0.92;
              }),
              line: {
                color: ns.map((n) =>
                  n.cl_id === selId
                    ? cssVar("--plot-node-selected")
                    : cssVar("--plot-node-line"),
                ),
                width: ns.map((n) => (n.cl_id === selId ? 2.5 : 0.5)),
              },
            },
          };
        })
        .filter(Boolean);

      const layout = {
        margin: { l: 8, r: 8, t: 8, b: 8 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        xaxis: { visible: false, fixedrange: false },
        yaxis: { visible: false, scaleanchor: "x", fixedrange: false },
        showlegend: true,
        legend: {
          font: { size: 10, color: cssVar("--plot-text") },
          bgcolor: "rgba(0,0,0,0)",
          orientation: "v",
        },
        hoverlabel: {
          bgcolor: cssVar("--plot-hover-bg"),
          font: { color: cssVar("--plot-hover-text") },
        },
        dragmode: "pan",
      };

      const data = [edgeTrace, hotEdgeTrace, ...nodeTraces];
      await Plotly.react(ref.current, data as never, layout as never, {
        responsive: true,
        displaylogo: false,
        scrollZoom: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
      });

      // Plotly.react drops user handlers on redraw, so re-bind after every draw.
      // The handler reads clickRef, so it always sees the latest state.
      const el = ref.current as unknown as {
        on: (
          ev: string,
          cb: (d: { points?: { customdata?: string }[] }) => void,
        ) => void;
        removeAllListeners?: (ev: string) => void;
      };
      el.removeAllListeners?.("plotly_click");
      el.on("plotly_click", (d) => {
        const cd = d.points?.[0]?.customdata;
        if (typeof cd === "string") clickRef.current(cd);
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [graph, organColor, selected, search, nodeById, theme]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el && plotlyRef.current) plotlyRef.current.purge(el);
    };
  }, []);

  return <div ref={ref} className="graph-canvas" />;
}

function NodePanel({
  node,
  graph,
  organColor,
  onPick,
}: {
  node: GraphNode;
  graph: RelationshipGraph;
  organColor: Map<string, string>;
  onPick: (n: GraphNode) => void;
}) {
  const nodeById = useMemo(
    () => new Map(graph.nodes.map((n) => [n.cl_id, n])),
    [graph],
  );

  const neighbors = useMemo(() => {
    const out: { node: GraphNode; sim: number }[] = [];
    for (const e of graph.edges) {
      const other =
        e.source === node.cl_id
          ? e.target
          : e.target === node.cl_id
            ? e.source
            : null;
      if (!other) continue;
      const n = nodeById.get(other);
      if (n) out.push({ node: n, sim: e.similarity });
    }
    return out.sort((a, b) => b.sim - a.sim);
  }, [graph, node, nodeById]);

  const [edge, setEdge] = useState<EdgeDetail | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  const openEdge = useCallback(
    (neighbor: GraphNode) => {
      setPicked(neighbor.cl_id);
      setEdge(null);
      fetchEdgeDetail(node.cl_id, neighbor.cl_id)
        .then(setEdge)
        .catch(() => setEdge(null));
    },
    [node],
  );

  return (
    <div className="node-panel">
      <div className="node-head">
        <span
          className="node-dot"
          style={{ background: organColor.get(node.primary_organ) ?? "#888" }}
        />
        <div>
          <h3>{node.label}</h3>
          <p className="muted mono">{node.cl_id}</p>
        </div>
      </div>
      <p className="muted note">
        {node.primary_organ} · in {node.n_organs} organ
        {node.n_organs > 1 ? "s" : ""} · {node.total_cells.toLocaleString()}{" "}
        cells
      </p>

      <h4 className="section-label">
        Nearest relatives <span className="count">{neighbors.length}</span>
      </h4>
      <div className="neighbor-list">
        {neighbors.length === 0 && (
          <p className="muted note">
            No links above the current similarity floor.
          </p>
        )}
        {neighbors.map(({ node: nb, sim }) => (
          <div key={nb.cl_id} className="neighbor">
            <button
              className={`neighbor-row ${picked === nb.cl_id ? "active" : ""}`}
              onClick={() => openEdge(nb)}
            >
              <span
                className="node-dot sm"
                style={{
                  background: organColor.get(nb.primary_organ) ?? "#888",
                }}
              />
              <span className="neighbor-label">{nb.label}</span>
              <span className="sim-badge">{sim.toFixed(2)}</span>
            </button>
            {picked === nb.cl_id && (
              <div className="edge-detail">
                {!edge ? (
                  <p className="muted note">Loading shared genes…</p>
                ) : edge.shared_genes.length === 0 ? (
                  <p className="muted note">No shared top markers.</p>
                ) : (
                  <>
                    <p className="helper note">
                      Genes defining <b>both</b> types (edge basis):
                    </p>
                    <div className="chip-row">
                      {edge.shared_genes.map((g) => (
                        <span
                          key={g.gene}
                          className="gene-chip"
                          title={`${node.label}: ${g.source_coef.toFixed(2)} · ${nb.label}: ${g.target_coef.toFixed(2)}`}
                        >
                          {g.gene}
                        </span>
                      ))}
                    </div>
                    <button className="focus-btn" onClick={() => onPick(nb)}>
                      Focus {nb.label} →
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
