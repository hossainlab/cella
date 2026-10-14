"""Marker-panel benchmark: coefficient vs DE markers (see cella.analysis.panel_benchmark).

Runs leave-one-dataset-out per organ, caching each organ's result so a rerun
only computes what is missing:

    data/processed/benchmark_panels/<Organ>.parquet           per (split, method, k) F1
    data/processed/benchmark_panels/<Organ>__markers.parquet  the marker lists scored
"""

from __future__ import annotations

import sys

import pandas as pd

from cella.analysis.panel_benchmark import OUT_DIR, run_organ
from cella.core.config import ORGANS


def main(organs: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for organ in organs:
        path = OUT_DIR / f"{organ.replace(' ', '_')}.parquet"
        if not path.exists():
            print(f"{organ}: running", flush=True)
            run_organ(organ).to_parquet(path)
        frames.append(pd.read_parquet(path))
    res = pd.concat(frames, ignore_index=True)
    summary = res.groupby(["method", "k"])[["lr_f1", "marker_f1", "panel_size"]].mean().round(3)
    print(summary.to_string())


if __name__ == "__main__":
    main(sys.argv[1:] or list(ORGANS))
