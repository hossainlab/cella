"use client";

import { useEffect, useRef, useState } from "react";
import { plotlyThemeLayout, useResolvedTheme } from "@/lib/theme";

interface Figure {
  data: unknown[];
  layout: Record<string, unknown>;
}

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

/** Fetches a Plotly figure (built in Python) as JSON and renders it interactively. */
export default function PlotlyChart({ url }: { url: string }) {
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
        const [res, mod] = await Promise.all([
          fetch(url),
          import("plotly.js-dist-min"),
        ]);
        if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
        const fig = (await res.json()) as Figure;
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
  }, [url]);

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
