"use client";

import { useEffect, useRef, useState } from "react";

interface Figure {
  data: unknown[];
  layout: Record<string, unknown>;
}

/** Fetches a Plotly figure (built in Python) as JSON and renders it interactively. */
export default function PlotlyChart({ url }: { url: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
        await Plotly.newPlot(el, fig.data, fig.layout, {
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

  return (
    <div className="plotly-wrap">
      {loading && <div className="detail-placeholder">Rendering figure…</div>}
      {err && <p className="error">{err}</p>}
      <div ref={ref} style={{ width: "100%" }} />
    </div>
  );
}
