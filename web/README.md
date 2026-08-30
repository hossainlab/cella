# Frontend (Next.js) — Discriminative Marker Atlas

The web client for the first v1 tool, built on the FastAPI endpoints. App Router,
TypeScript, no UI framework (hand-rolled CSS, light/dark aware).

## Run

The frontend proxies `/api/*` to the backend (see `next.config.mjs`), so start
both:

```bash
# 1. backend (from repo root)
uv run --group api uvicorn cella.api.main:app --port 8137

# 2. frontend (from web/)
npm install
npm run dev            # http://localhost:3000
```

Override the backend target with `API_BASE` if it runs elsewhere.

## Layout

```
app/
  layout.tsx        root layout + metadata
  page.tsx          Marker Atlas: search -> per-organ markers + consensus
  globals.css       theme (light/dark)
lib/
  api.ts            typed client for the FastAPI endpoints
  types.ts          response types mirroring cella.api.schemas
next.config.mjs     /api -> backend proxy (no CORS)
```

## What it shows

Search a cell type → its **universal core identity** (consensus genes,
discriminative in every organ) vs. **tissue-adapted** per-organ markers
(organ-specific genes highlighted). Data comes from CellTypist classifier weights.

Planned next tools (own routes): Fingerprint Explorer, Relationship Graph.
