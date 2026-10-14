"use client";

import { useEffect, useRef, useState } from "react";
import { fetchOrganFigure } from "@/lib/api";
import { plotlyThemeLayout, useResolvedTheme } from "@/lib/theme";

interface Figure {
  data: unknown[];
  layout: Record<string, unknown>;
}

type FigureProps = Parameters<typeof fetchOrganFigure>;

/** Deep-merge theme overrides into a figure layout (axes keep their own settings). */
function themed(layout: Record<string, unknown>): Record<string, unknown> {
  const theme = plotlyThemeLayout();
  const out: Record<string, unknown> = { ...layout };
  for (const [key, value] of Object.entries(theme)) {
    const base = layout[key];
    out[key] =
      base && typeof base === "object" && value && typeof value === "object"
        ? { ...(base as object), ...(value as object) }
        : value;
  }
  // Subplot axes (xaxis2, yaxis3, ...) get the same colors as the primary ones.
  for (const key of Object.keys(layout)) {
    if (/^[xy]axis\d+$/.test(key)) {
      out[key] = {
        ...(layout[key] as object),
        ...(theme[key.slice(0, 5)] as object),
      };
    }
  }
  return out;
}

/**
 * Renders an Organ Browser Plotly figure interactively. The figure comes from the
 * API (built in Python) or, in static mode, from an exported file or the browser.
 */
export default function PlotlyChart({
  slug,
  kind,
  collection,
  genes,
}: {
  slug: FigureProps[0];
  kind: FigureProps[1];
  collection?: string;
  genes?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const theme = useResolvedTheme();
  const layoutRef = useRef<Record<string, unknown> | null>(null);

  useEffect(() => {
    let purge: (() => void) | undefined;
    let cancelled = false;

    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const [fig, mod] = await Promise.all([
          fetchOrganFigure(slug, kind, {
            collection,
            genes,
          }) as Promise<Figure>,
          import("plotly.js-dist-min"),
        ]);
        if (cancelled || !ref.current) return;
        const Plotly = mod.default;
        const el = ref.current;
        layoutRef.current = fig.layout;
        await Plotly.newPlot(el, fig.data, themed(fig.layout), {
          responsive: true,
          displaylogo: false,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
        });
        purge = () => Plotly.purge(el);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      purge?.();
    };
  }, [slug, kind, collection, genes]);

  // Recolor in place when the theme flips; no refetch.
  useEffect(() => {
    const el = ref.current;
    const layout = layoutRef.current;
    if (!el || !layout) return;
    import("plotly.js-dist-min").then((mod) => {
      if (ref.current === el) mod.default.relayout(el, themed(layout));
    });
  }, [theme]);

  return (
    <div className="plotly-wrap">
      {loading && <div className="detail-placeholder">Rendering figure…</div>}
      {err && <p className="error">{err}</p>}
      <div ref={ref} style={{ width: "100%" }} />
    </div>
  );
}
