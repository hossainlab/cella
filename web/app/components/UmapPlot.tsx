"use client";

import { useEffect, useRef, useState } from "react";
import { categoryColor } from "@/lib/palette";
import type { OrganEmbedding } from "@/lib/types";

const W = 560;
const H = 460;
const PAD = 12;

export default function UmapPlot({ emb }: { emb: OrganEmbedding }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<number | null>(null); // hovered cell-type index

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const { x, y, c } = emb;
    const minX = Math.min(...x);
    const maxX = Math.max(...x);
    const minY = Math.min(...y);
    const maxY = Math.max(...y);
    const sx = (W - 2 * PAD) / (maxX - minX || 1);
    const sy = (H - 2 * PAD) / (maxY - minY || 1);

    for (let i = 0; i < x.length; i++) {
      const px = PAD + (x[i] - minX) * sx;
      // invert y so up is positive
      const py = H - PAD - (y[i] - minY) * sy;
      const active = hover === null || hover === c[i];
      ctx.fillStyle = active
        ? categoryColor(c[i])
        : "rgba(140,140,150,0.10)";
      ctx.globalAlpha = active ? 0.75 : 1;
      ctx.beginPath();
      ctx.arc(px, py, active && hover !== null ? 2.2 : 1.6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }, [emb, hover]);

  return (
    <div className="umap">
      <canvas
        ref={canvasRef}
        style={{ width: W, height: H, maxWidth: "100%" }}
        className="umap-canvas"
      />
      <div className="umap-legend">
        {emb.cell_types.map((ct, i) => (
          <button
            key={ct}
            className={`umap-leg-item ${hover === i ? "on" : ""}`}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <span
              className="umap-swatch"
              style={{ background: categoryColor(i) }}
            />
            {ct}
          </button>
        ))}
      </div>
    </div>
  );
}
