"""Pipeline CLI entry point: ``uv run cella <command>``.

Thin Typer wrapper over the pipeline stages. Each command maps to a phase in
docs/CONCEPT.md §9. Bodies are stubs until each phase is implemented.
"""

from __future__ import annotations

import typer

from cella.core.config import ORGANS, settings

app = typer.Typer(help="Cella data pipeline.")


@app.command()
def info() -> None:
    """Print the resolved configuration and the organs in scope."""
    typer.echo(f"atlas_release : {settings.atlas_release}")
    typer.echo(f"raw_dir       : {settings.raw_dir}")
    typer.echo(f"processed_dir : {settings.processed_dir}")
    typer.echo(f"organs ({len(ORGANS)}) : {', '.join(ORGANS)}")


@app.command()
def acquire(
    what: str = typer.Argument(
        "all",
        help="What to acquire: 'models', 'obs', 'atlases' (~30 GB full .h5ad), or 'all'.",
    ),
    organ: list[str] | None = typer.Option(
        None,
        "--organ",
        "-o",
        help="Limit to specific organs (repeatable). Default: all 12.",
    ),
    force: bool = typer.Option(False, "--force", help="Re-fetch even if present."),
) -> None:
    """P0 — acquire minimal local inputs into data/raw/ (models + cached .obs, ~50 MB)."""
    from cella.pipeline import acquire as acq

    organs = tuple(organ) if organ else ORGANS
    if what == "models":
        acq.acquire_models(organs, force=force)
    elif what == "obs":
        acq.cache_obs(organs, force=force)
    elif what == "atlases":
        acq.acquire_atlases(organs, force=force)
    elif what == "all":
        acq.acquire_all(organs, force=force)
    else:
        raise typer.BadParameter("what must be 'models', 'obs', 'atlases', or 'all'")
    typer.echo(f"done: {what} ({len(organs)} organ(s)) -> {settings.raw_dir}")


@app.command()
def build(top_n: int = typer.Option(25, help="Top-N markers per direction per cell type.")) -> None:
    """P1 — harmonize + emit artifacts (registry, counts, weights, markers)."""
    from cella.pipeline.emit import emit_all

    emit_all(top_n=top_n)


@app.command()
def derive(
    organ: list[str] | None = typer.Option(None, "--organ", "-o", help="Limit organs."),
) -> None:
    """Organ Browser — compute pseudobulk, UMAP embeddings, and TF activity."""
    from cella.pipeline.derive import (
        derive_cci,
        derive_embeddings,
        derive_expression,
        derive_gsea,
        derive_tf,
    )

    organs = tuple(organ) if organ else ORGANS
    derive_expression(organs)
    derive_embeddings(organs)
    derive_tf(organs)
    derive_gsea(organs)
    derive_cci(organs)


@app.command()
def graph() -> None:
    """P4 — recompute the cross-tissue relationship graph."""
    from cella.pipeline.graph import build_relationship_graph

    build_relationship_graph()


if __name__ == "__main__":
    app()
