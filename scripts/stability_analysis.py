"""Measure replicate stability of classifier coefficients, per organ and cell type.

Answers the obvious objection to the invariance result: a low cross-organ
cosine means organ adaptation only if the coefficients are reproducible in the
first place. Each organ's classifier is retrained on disjoint, equally sized
folds of cells and the replicate-to-replicate cosine is recorded per cell type.

Writes data/processed/stability_cell_type_organ.parquet.

Run: uv run python scripts/stability_analysis.py
"""

from __future__ import annotations

import sys
import time
import warnings

import pandas as pd

from cella.analysis.invariance import PROCESSED
from cella.analysis.stability import (
    CELLS_PER_TYPE,
    N_REPLICATES,
    published_agreement,
    replicate_stability,
    train_replicates,
)

warnings.filterwarnings("ignore")


def main() -> None:
    cto = pd.read_parquet(PROCESSED / "cell_type_organ.parquet")
    organs = sorted(cto["organ"].unique())
    if len(sys.argv) > 1:
        organs = [o for o in organs if o in set(sys.argv[1:])]

    print(
        f"{N_REPLICATES} replicates x {CELLS_PER_TYPE} cells per cell type, "
        f"disjoint folds, {len(organs)} organs"
    )
    frames = []
    for organ in organs:
        start = time.time()
        replicates = train_replicates(organ, n_replicates=N_REPLICATES)
        frame = replicate_stability(replicates).merge(
            published_agreement(replicates), on=["organ", "curated_label"], how="left"
        )
        frames.append(frame)
        n_ok = int(frame["eligible"].sum())
        print(
            f"  {organ:16s} {len(frame):3d} cell types "
            f"({n_ok} scored) {time.time() - start:6.1f}s",
            flush=True,
        )

    stability = pd.concat(frames, ignore_index=True)
    stability = stability.merge(
        cto[["organ", "curated_label", "cl_id", "cell_count"]],
        on=["organ", "curated_label"],
        how="left",
    )
    stability.to_parquet(PROCESSED / "stability_cell_type_organ.parquet", index=False)
    print(f"\nwrote {PROCESSED / 'stability_cell_type_organ.parquet'}  ({len(stability)} rows)")

    scored = stability[stability["eligible"]]
    print(f"{len(scored)} (organ, cell type) pairs scored at matched n")
    print(f"stability: median {scored['stability'].median():.3f}  "
          f"IQR {scored['stability'].quantile(.25):.3f}-{scored['stability'].quantile(.75):.3f}")


if __name__ == "__main__":
    main()
