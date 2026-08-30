"use client";

import type { StackedComposition } from "@/lib/types";

export default function StackedBar({
  comp,
  colorOf,
}: {
  comp: StackedComposition;
  colorOf: (name: string) => string;
}) {
  return (
    <div className="stacked">
      <div className="stacked-yaxis">
        {[1, 0.75, 0.5, 0.25, 0].map((t) => (
          <span key={t}>{t.toFixed(2)}</span>
        ))}
      </div>
      <div className="stacked-cols">
        {comp.groups.map((g, gi) => (
          <div className="stacked-col" key={g}>
            <div className="stacked-bar">
              {comp.cell_types.map((ct, ti) => {
                const frac = comp.data[gi][ti];
                if (frac <= 0) return null;
                return (
                  <span
                    key={ct}
                    className="stacked-seg"
                    style={{
                      height: `${frac * 100}%`,
                      background: colorOf(ct),
                    }}
                    title={`${ct}: ${(frac * 100).toFixed(1)}%`}
                  />
                );
              })}
            </div>
            <span className="stacked-label" title={g}>
              {g}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
