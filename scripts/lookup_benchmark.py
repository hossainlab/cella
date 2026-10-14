"""Benchmark reverse lookup against external marker sets (see cella.analysis.lookup_benchmark).

Downloads the Enrichr libraries on first run, then writes:

    data/processed/benchmark_lookup.parquet           per (query, method) ranks, full queries
    data/processed/benchmark_lookup_subsample.parquet same, queries cut to k = 3/5/10 genes

and prints the calibration table behind the API's confidence thresholds.
"""

from __future__ import annotations

import urllib.request

import numpy as np
import pandas as pd

from cella.analysis.lookup_benchmark import (
    DEV_LIBRARY,
    ENRICHR_URL,
    EXTERNAL,
    LIBRARIES,
    PROCESSED,
    build_index,
    confidence_calibration,
    evaluate,
    load_queries,
    summarize,
)

SUBSAMPLE_K = (3, 5, 10)
SUBSAMPLE_DRAWS = 5


def fetch_libraries() -> None:
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    for library in LIBRARIES:
        path = EXTERNAL / f"{library}.gmt"
        if not path.exists():
            urllib.request.urlretrieve(ENRICHR_URL.format(library), path)  # noqa: S310


def main() -> None:
    fetch_libraries()
    queries, accounting = load_queries()
    print(accounting.to_string(index=False), "\n")
    index = build_index()

    full = evaluate(queries, index)
    full.to_parquet(PROCESSED / "benchmark_lookup.parquet")
    per_stratum = full.groupby("stratum")["term"].nunique().to_dict()
    print(f"scored queries: {full['term'].nunique()} ({per_stratum})\n")
    for stratum, sub in full.groupby("stratum"):
        print(f"== {stratum}")
        print(summarize(sub).round(3).to_string(index=False), "\n")
    print(f"== independent, dev library ({DEV_LIBRARY}) vs held-out libraries")
    ind_split = full[full["stratum"] == "independent"].assign(
        split=lambda d: np.where(d["library"] == DEV_LIBRARY, "dev", "test")
    )
    print(summarize(ind_split, by=("split", "method")).round(3).to_string(index=False), "\n")
    print("== independent, by library")
    ind = full[full["stratum"] == "independent"]
    print(summarize(ind, by=("library", "method")).round(3).to_string(index=False), "\n")

    print("== reverse-lookup confidence call (expr_pct), thresholds chosen on dev")
    print(confidence_calibration(queries, index).round(3).to_string(index=False), "\n")

    frames = []
    for k in SUBSAMPLE_K:
        for draw in range(SUBSAMPLE_DRAWS):
            res = evaluate(queries, index, subsample=k, seed=draw)
            frames.append(res.assign(k=k, draw=draw))
    sub = pd.concat(frames, ignore_index=True)
    sub.to_parquet(PROCESSED / "benchmark_lookup_subsample.parquet")
    print("== independent, subsampled queries")
    sub_ind = sub[sub["stratum"] == "independent"]
    print(summarize(sub_ind, by=("k", "method")).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
