"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { listOrgans } from "@/lib/api";
import type { OrganSummary } from "@/lib/types";

type SortKey = keyof Pick<
  OrganSummary,
  "organ" | "n_cells" | "n_cell_types" | "n_datasets" | "n_donors"
>;

const COLS: { key: SortKey; label: string; num: boolean }[] = [
  { key: "organ", label: "Organ", num: false },
  { key: "n_cells", label: "Cells", num: true },
  { key: "n_cell_types", label: "Cell types", num: true },
  { key: "n_datasets", label: "Datasets", num: true },
  { key: "n_donors", label: "Donors", num: true },
];

const ORGAN_ICONS: Record<string, string> = {
  Heart: "🫀",
  Lung: "🫁",
  Liver: "🩺",
  Kidney: "🫘",
  Blood: "🩸",
  Hippocampus: "🧠",
  Intestine: "🦠",
  Pancreas: "🧫",
  Spleen: "🛡️",
  "Bone marrow": "🦴",
  "Lymph node": "🔬",
  "Skeletal muscle": "💪",
};

export default function OrgansPage() {
  const router = useRouter();
  const [organs, setOrgans] = useState<OrganSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("n_cells");
  const [asc, setAsc] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  useEffect(() => {
    listOrgans().then(setOrgans).catch((e) => setError(String(e)));
  }, []);

  const rows = useMemo(() => {
    const filtered = organs.filter((o) =>
      o.organ.toLowerCase().includes(q.trim().toLowerCase()),
    );
    const sorted = [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return asc ? cmp : -cmp;
    });
    return sorted;
  }, [organs, q, sortKey, asc]);

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(k === "organ");
    }
  };

  return (
    <div className="wrap">
      <header>
        <p className="eyebrow">Interactive Tissue Atlases</p>
        <h1 style={{ fontSize: "2.4rem", margin: "0.2rem 0 0.85rem", letterSpacing: "-0.02em" }}>
          Human Organ Browser
        </h1>
        <p className="sub" style={{ maxWidth: "68ch", fontSize: "1.05rem" }}>
          Explore 12 deeply curated human organ atlases harmonized from 38 datasets.
          Inspect cell composition, 25k UMAP manifolds, transcription factor regulons, and cell-cell interactomes.
        </p>
      </header>

      {error && <p className="error">Error: {error}</p>}

      <div className="view-toggle-bar">
        <form className="atlas-search" style={{ margin: 0, flex: 1, maxWidth: "420px" }} onSubmit={(e) => e.preventDefault()} role="search">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search organs (e.g. Lung, Brain, Blood)…"
            aria-label="Filter organs"
          />
        </form>

        <div className="view-toggle">
          <button
            type="button"
            className={`view-btn ${viewMode === "grid" ? "active" : ""}`}
            onClick={() => setViewMode("grid")}
          >
            <span>⊞</span> Grid View
          </button>
          <button
            type="button"
            className={`view-btn ${viewMode === "table" ? "active" : ""}`}
            onClick={() => setViewMode("table")}
          >
            <span>☰</span> Table View
          </button>
        </div>
      </div>

      <p className="helper mb">
        Showing {rows.length} of {organs.length} human organ atlases.
      </p>

      {viewMode === "grid" ? (
        <div className="organ-grid-modern">
          {rows.map((o) => {
            const icon = ORGAN_ICONS[o.organ] || "🧬";
            return (
              <Link key={o.slug} href={`/organs/${o.slug}`} className="organ-card-modern">
                <div className="organ-card-header">
                  <div className="organ-title-wrap">
                    <h3 className="organ-name">{o.organ}</h3>
                    <span className="organ-cell-count">{o.n_cells.toLocaleString()} cells</span>
                  </div>
                  <div className="organ-icon-circle">{icon}</div>
                </div>

                <div className="organ-metrics-grid">
                  <div className="organ-metric-item">
                    <span className="organ-metric-val">{o.n_cell_types}</span>
                    <span className="organ-metric-lbl">Cell Types</span>
                  </div>
                  <div className="organ-metric-item">
                    <span className="organ-metric-val">{o.n_datasets}</span>
                    <span className="organ-metric-lbl">Datasets</span>
                  </div>
                  <div className="organ-metric-item">
                    <span className="organ-metric-val">{o.n_donors}</span>
                    <span className="organ-metric-lbl">Donors</span>
                  </div>
                </div>

                <div className="organ-card-footer">
                  <span>Explore Atlas</span>
                  <span>→</span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    className={`${c.num ? "num" : ""} ${sortKey === c.key ? "sorted" : ""}`}
                    onClick={() => toggleSort(c.key)}
                  >
                    {c.label}
                    <span className="arrow">
                      {sortKey === c.key ? (asc ? " ▲" : " ▼") : ""}
                    </span>
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr
                  key={o.slug}
                  className="data-row"
                  onClick={() => {
                    router.push(`/organs/${o.slug}`);
                  }}
                >
                  <td className="organ-name">
                    <span style={{ marginRight: "0.5rem" }}>{ORGAN_ICONS[o.organ] || "🧬"}</span>
                    {o.organ}
                  </td>
                  <td className="num">{o.n_cells.toLocaleString()}</td>
                  <td className="num">{o.n_cell_types}</td>
                  <td className="num">{o.n_datasets}</td>
                  <td className="num">{o.n_donors}</td>
                  <td className="num">
                    <Link
                      href={`/organs/${o.slug}`}
                      className="row-open"
                      onClick={(e) => e.stopPropagation()}
                    >
                      open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
