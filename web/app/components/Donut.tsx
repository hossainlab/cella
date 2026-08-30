"use client";

export interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

const SIZE = 220;
const R = 100;
const INNER = 58;

function arc(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const p0x = cx + r * Math.cos(a0);
  const p0y = cy + r * Math.sin(a0);
  const p1x = cx + r * Math.cos(a1);
  const p1y = cy + r * Math.sin(a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${p0x} ${p0y} A ${r} ${r} 0 ${large} 1 ${p1x} ${p1y}`;
}

export default function Donut({ slices }: { slices: DonutSlice[] }) {
  const total = slices.reduce((s, d) => s + d.value, 0) || 1;
  let angle = -Math.PI / 2;
  const cx = SIZE / 2;
  const cy = SIZE / 2;
  const mid = (R + INNER) / 2;
  const width = R - INNER;

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      width={SIZE}
      height={SIZE}
      className="donut"
    >
      {slices.map((d) => {
        const frac = d.value / total;
        const a0 = angle;
        const a1 = angle + frac * Math.PI * 2;
        angle = a1;
        // full-circle guard
        const path =
          frac >= 0.9999
            ? `M ${cx} ${cy - mid} A ${mid} ${mid} 0 1 1 ${cx - 0.01} ${cy - mid}`
            : arc(cx, cy, mid, a0, a1);
        return (
          <path
            key={d.label}
            d={path}
            fill="none"
            stroke={d.color}
            strokeWidth={width}
          >
            <title>
              {d.label}: {((100 * d.value) / total).toFixed(1)}%
            </title>
          </path>
        );
      })}
    </svg>
  );
}
