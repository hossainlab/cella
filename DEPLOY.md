# Deploying Cella

Cella builds in two modes from one codebase. The mode is chosen at build time
with `NEXT_PUBLIC_DATA_MODE`; every page and result is the same in both.

| | Static mode (public site) | Server mode |
|---|---|---|
| Backend | none | FastAPI (`cella.api`) |
| Data | files written by `cella export` | Parquet artifacts in `data/processed/` |
| Free-text queries (reverse lookup, gene, signature) | computed in the browser | computed by the API |
| Hosting | any static host — GitHub Pages, Cloudflare Pages | any host that runs Python (Docker) |
| Cost | free | depends on the host |
| Programmatic API (`/docs`) | no | yes |

## Static mode — GitHub Pages (current public deployment)

Deployment is automatic: `.github/workflows/pages.yml` runs on every push to
`main` (or manually via *Actions → Deploy static site to GitHub Pages → Run
workflow*). It exports the data, builds the static site and publishes it to
`https://<owner>.github.io/<repo>/`.

One-time setup: *Settings → Pages → Source: GitHub Actions*.

Build it locally:

```bash
uv run --group api cella export --out web/public/data   # ~1 min, ~57 MB
cd web
NEXT_PUBLIC_DATA_MODE=static NEXT_PUBLIC_BASE_PATH=/cella npx next build
# output in web/out/ — serve it under /cella to preview:
mkdir -p /tmp/pages && cp -R out /tmp/pages/cella && python3 -m http.server -d /tmp/pages 8090
# open http://localhost:8090/cella/
```

`NEXT_PUBLIC_BASE_PATH` is the sub-path the site is served from: `/<repo>` for
a GitHub project site, empty for a custom domain or a user site.

### Checking that static and server mode agree

Static files are the API's own responses (the exporter calls the FastAPI app
in-process). The browser re-implementations of the free-text endpoints are
checked against the live API:

```bash
uv run --group api uvicorn cella.api.main:app --port 8137 &
uv run --group api cella export --out web/public/data
cd web && npx tsx scripts/check-static.ts
```

Expression values are quantized in the export (fraction expressing to 1/255,
mean expression to 1/65535 of the organ maximum), so numeric results agree to
about 0.002; rankings can differ only between hits that tie at that precision.
In static mode, reverse-lookup hits show a gene's classifier weight only when
the gene is among the stored top markers (the server reads the full matrix).

## Server mode — local or on a server

Local development:

```bash
uv run --group api uvicorn cella.api.main:app --port 8137 --reload
cd web && npm run dev            # http://localhost:3000, proxies /api to :8137
```

On a server, run the API from the `Dockerfile` (it reads `$PORT`) and build the
frontend with `API_BASE` pointing at it:

```bash
docker build -t cella-api . && docker run -p 8137:10000 cella-api
cd web && API_BASE=https://api.example.org npm run build && npm start
```

The API keeps every pseudobulk matrix it has read in memory, so allow roughly
1-2 GB of RAM.

## Updating the site after a data change

1. Rebuild artifacts as usual (`cella build`, `cella graph`, ...).
2. Commit the changed files in `data/processed/` and push to `main`.
3. The workflow re-exports and redeploys; nothing else to do.
