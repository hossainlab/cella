"""Rank cell types by how organ-invariant their discriminative identity is.

Writes:
  data/processed/invariance_scores.parquet   one row per multi-organ cell type
  data/processed/invariance_pairs.parquet    every cross-organ cosine (signal + null)

Run: uv run python scripts/invariance_analysis.py
"""

from __future__ import annotations

import itertools
import warnings

import pandas as pd

from cella.analysis.invariance import (
    PROCESSED,
    assign_lineages,
    cell_type_vectors,
    core_fraction,
    load_organ,
    low_granularity_terms,
    mean_pairwise_jaccard,
    pair_cosines,
)

warnings.filterwarnings("ignore", message=".*InconsistentVersion.*")

TOP_K = 50


def main() -> None:
    cto = pd.read_parquet(PROCESSED / "cell_type_organ.parquet")
    registry = pd.read_parquet(PROCESSED / "registry.parquet")
    organs = sorted(cto["organ"].unique())

    print(f"loading {len(organs)} organ models ...")
    models = {o: load_organ(o) for o in organs}
    vectors = cell_type_vectors(models, cto)
    print(f"  {len(vectors)} (organ, cell type) weight vectors")

    print("computing cross-organ cosines ...")
    frames = [pair_cosines(models, vectors, a, b)[0] for a, b in itertools.combinations(organs, 2)]
    pairs = pd.concat(frames, ignore_index=True)
    pairs["matched"] = pairs["cl_a"] == pairs["cl_b"]
    pairs.to_parquet(PROCESSED / "invariance_pairs.parquet", index=False)

    null = pairs.loc[~pairs["matched"], "cosine"]
    null_mu, null_sd = null.mean(), null.std()
    print(f"  null (mismatched cell types, n={len(null):,}): mean={null_mu:.4f} sd={null_sd:.4f}")

    signal = pairs.loc[pairs["matched"]].copy()
    print(f"  signal (same cell type across organs, n={len(signal):,})")

    organ_map = (
        cto.groupby("cl_id")["organ"].apply(lambda s: sorted(set(s))).rename("organs")
    )

    rows = []
    for cl_id, grp in signal.groupby("cl_id" if "cl_id" in signal else "cl_a"):
        organs_here = organ_map.loc[cl_id]
        frac, core_genes = core_fraction(models, vectors, cl_id, organs_here, top_k=TOP_K)
        jaccard = mean_pairwise_jaccard(models, vectors, cl_id, organs_here, top_k=TOP_K)
        rows.append(
            {
                "cl_id": cl_id,
                "n_organs": len(organs_here),
                "n_organ_pairs": len(grp),
                "mean_cosine": grp["cosine"].mean(),
                "min_cosine": grp["cosine"].min(),
                "max_cosine": grp["cosine"].max(),
                "z_vs_null": (grp["cosine"].mean() - null_mu) / null_sd,
                "core_fraction": frac,
                "mean_top50_jaccard": jaccard,
                "mean_labels_per_organ": float(
                    cto[cto["cl_id"] == cl_id].groupby("organ").size().mean()
                ),
                "core_genes": "|".join(core_genes),
                "organs": ", ".join(organs_here),
            }
        )

    scores = pd.DataFrame(rows).merge(
        registry[["cl_id", "ontology_label", "total_cells"]], on="cl_id", how="left"
    )
    coarse = low_granularity_terms(sorted(registry["cl_id"]))
    scores["lineage"] = scores["cl_id"].map(assign_lineages(sorted(scores["cl_id"])))
    scores["low_granularity"] = scores["cl_id"].isin(coarse)
    scores = scores.sort_values("mean_cosine", ascending=False).reset_index(drop=True)
    scores.attrs["null_mean"] = float(null_mu)
    scores.attrs["null_sd"] = float(null_sd)
    scores.to_parquet(PROCESSED / "invariance_scores.parquet", index=False)

    print(f"\n{len(scores)} multi-organ cell types scored\n")
    cols = [
        "ontology_label",
        "n_organs",
        "mean_cosine",
        "z_vs_null",
        "mean_top50_jaccard",
        "core_fraction",
    ]
    specific = scores[~scores["low_granularity"]]
    print(
        f"{scores['low_granularity'].sum()} of {len(scores)} terms flagged low-granularity "
        f"(ancestor of another annotated term); {len(specific)} specific terms retained\n"
    )
    print("=== MOST organ-invariant (specific terms) ===")
    print(specific.head(12)[cols].to_string(index=False))
    print("\n=== MOST organ-adapted / plastic (specific terms) ===")
    print(specific.tail(12)[cols].to_string(index=False))
    print("\n=== by lineage (specific terms) ===")
    by_lineage = (
        specific.groupby("lineage")
        .agg(n=("cl_id", "size"), mean_cosine=("mean_cosine", "mean"),
             median_cosine=("mean_cosine", "median"))
        .sort_values("mean_cosine", ascending=False)
    )
    print(by_lineage.to_string())

    from scipy.stats import mannwhitneyu

    circulating = specific.loc[
        specific["lineage"].isin(["Lymphoid", "Myeloid", "Erythroid/Mega"]), "mean_cosine"
    ]
    resident = specific.loc[
        specific["lineage"].isin(["Mesenchymal/Stromal", "Endothelial", "Epithelial"]),
        "mean_cosine",
    ]
    stat, pval = mannwhitneyu(circulating, resident, alternative="greater")
    print(
        f"\ncirculating (n={len(circulating)}, median={circulating.median():.3f}) vs "
        f"tissue-resident (n={len(resident)}, median={resident.median():.3f}): "
        f"Mann-Whitney U={stat:.1f}, one-sided p={pval:.2e}"
    )

    print("\n=== excluded: low-granularity terms ===")
    print(
        scores[scores["low_granularity"]][cols].to_string(index=False)
    )


if __name__ == "__main__":
    main()
