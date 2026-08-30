"use client";

import Link from "next/link";
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

export default function OrgansPage() {
  const [organs, setOrgans] = useState<OrganSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("n_cells");
  const [asc, setAsc] = useState(false);

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
        <h1>Organ Browser</h1>
        <p className="sub">
          Browse the 12 harmonized human organ atlases. Each row is one organ —
          open it for source datasets, cell-type composition, and per-gene
          expression across cell types.
        </p>
      </header>

      {error && <p className="error">Error: {error}</p>}

      <form className="atlas-search" onSubmit={(e) => e.preventDefault()} role="search">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter organs…"
          aria-label="Filter organs"
        />
      </form>

      <p className="helper mb">
        {rows.length} organ{rows.length === 1 ? "" : "s"}. Click a column header to
        sort; click a row to open the atlas.
      </p>

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
                  window.location.href = `/organs/${o.slug}`;
                }}
              >
                <td className="organ-name">{o.organ}</td>
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
    </div>
  );
}
