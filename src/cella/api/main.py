"""FastAPI application entry point.

Run (after ``uv sync --group api``):
    uv run uvicorn cella.api.main:app --reload
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware

from cella import __version__
from cella.api.routers import (
    cell_types,
    fingerprints,
    graph,
    markers,
    organs,
    reverse_lookup,
)
from cella.core.config import settings

app = FastAPI(
    title="Cella API",
    version=__version__,
    summary="Discriminative cell-type identity across 12 human organ atlases.",
)

# Compress JSON payloads (graph/fingerprint responses shrink ~5x over the wire).
app.add_middleware(GZipMiddleware, minimum_size=500)

# All served data is precomputed and immutable per atlas release, so let browsers
# cache GET responses. The release stamp is the cache key: a new release changes
# the ETag, forcing revalidation; within a release, repeats are served locally.
_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"
_RELEASE_ETAG = f'"{settings.atlas_release}"'


@app.middleware("http")
async def cache_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if request.method == "GET" and request.url.path != "/health":
        response.headers["Cache-Control"] = _CACHE_CONTROL
        response.headers["ETag"] = _RELEASE_ETAG
        # Revalidation with the current release -> 304, skip resending the body.
        if (
            response.status_code == 200
            and request.headers.get("if-none-match") == _RELEASE_ETAG
        ):
            return Response(
                status_code=304,
                headers={"ETag": _RELEASE_ETAG, "Cache-Control": _CACHE_CONTROL},
            )
    return response


app.include_router(cell_types.router)
app.include_router(markers.router)
app.include_router(fingerprints.router)
app.include_router(graph.router)
app.include_router(organs.router)
app.include_router(reverse_lookup.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
