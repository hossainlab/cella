"""Rank cell types by how organ-invariant their discriminative identity is.

Writes:
  data/processed/invariance_scores.parquet   one row per multi-organ cell type
  data/processed/invariance_pairs.parquet    every cross-organ cosine (signal + null)

Run: uv run python scripts/invariance_analysis.py
"""

from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd

from cella.analysis.invariance import (
    PROCESSED,
    assign_lineages,
    cell_type_vectors,
    comparable_organs,
    core_fraction,
    load_organ,
    low_granularity_terms,
    mean_pairwise_jaccard,
    pair_cosines,
)

warnings.filterwarnings("ignore", message=".*InconsistentVersion.*")

TOP_K = 50

CIRCULATING = ["Lymphoid", "Erythroid/Mega", "Myeloid"]
RESIDENT = ["Epithelial", "Endothelial", "Mesenchymal/Stromal"]


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
    # A coarse term can still be compared across the organs where no subtype of
    # it was split out; those organs are "comparable" and give it a second-tier
    # score. CL:0000000 ("cell") is dropped outright as uninterpretable.
    comparable = comparable_organs(cto)
    scores["comparable_organs"] = scores["cl_id"].map(
        lambda c: ", ".join(comparable.get(c, []))
    )
    scores["n_comparable_organs"] = scores["cl_id"].map(lambda c: len(comparable.get(c, [])))

    comp_cos = []
    for row in scores.itertuples():
        allowed = set(comparable.get(row.cl_id, []))
        grp = signal[
            (signal["cl_a"] == row.cl_id)
            & signal["organ_a"].isin(allowed)
            & signal["organ_b"].isin(allowed)
        ]
        comp_cos.append(grp["cosine"].mean() if len(grp) else float("nan"))
    scores["mean_cosine_comparable"] = comp_cos

    coarse = low_granularity_terms(sorted(registry["cl_id"]))
    scores["lineage"] = scores["cl_id"].map(assign_lineages(sorted(scores["cl_id"])))
    scores["low_granularity"] = scores["cl_id"].isin(coarse)
    scores["tier"] = np.where(
        ~scores["low_granularity"],
        "specific",
        np.where(
            (scores["n_comparable_organs"] >= 2) & (scores["cl_id"] != "CL:0000000"),
            "granularity-resolved",
            "excluded",
        ),
    )
    # The tier-2 score is the one restricted to comparable organs; z must be
    # recomputed from whichever score the tier actually uses.
    scores["invariance"] = np.where(
        scores["tier"] == "granularity-resolved",
        scores["mean_cosine_comparable"],
        scores["mean_cosine"],
    )
    scores["z_vs_null"] = (scores["invariance"] - null_mu) / null_sd
    scores = scores.sort_values("invariance", ascending=False).reset_index(drop=True)
    scores.attrs["null_mean"] = float(null_mu)
    scores.attrs["null_sd"] = float(null_sd)
    scores.to_parquet(PROCESSED / "invariance_scores.parquet", index=False)

    print(f"\n{len(scores)} multi-organ cell types scored\n")
    cols = ["ontology_label", "lineage", "n_organs", "invariance", "z_vs_null"]
    tiers = scores["tier"].value_counts()
    print(
        f"tiers: {tiers.get('specific', 0)} specific, "
        f"{tiers.get('granularity-resolved', 0)} granularity-resolved, "
        f"{tiers.get('excluded', 0)} excluded\n"
    )

    specific = scores[scores["tier"] == "specific"]
    resolved = scores[scores["tier"] == "granularity-resolved"].copy()
    resolved["n_organs"] = resolved["n_comparable_organs"]

    print("=== TIER 1: specific terms, most organ-invariant ===")
    print(specific.head(8)[cols].to_string(index=False))
    print("\n=== TIER 1: most organ-adapted ===")
    print(specific.tail(8)[cols].to_string(index=False))

    print("\n=== TIER 2: coarse terms rescued on comparable organs only ===")
    print(resolved[cols + ["comparable_organs"]].to_string(index=False))

    print("\n=== EXCLUDED (<2 comparable organs, or CL:0000000) ===")
    excluded = scores[scores["tier"] == "excluded"]
    print(excluded[["ontology_label", "n_comparable_organs"]].to_string(index=False))

    from scipy.stats import mannwhitneyu, spearmanr

    def split(frame):
        circ = frame.loc[frame["lineage"].isin(CIRCULATING), "invariance"]
        res = frame.loc[frame["lineage"].isin(RESIDENT), "invariance"]
        return circ, res

    print("\n=== circulating vs tissue-resident ===")
    for name, frame in [
        ("tier 1 (specific)", specific),
        ("tier 2 (resolved)", resolved),
        ("tier 1 + 2", pd.concat([specific, resolved])),
    ]:
        circ, res = split(frame)
        if len(circ) < 2 or len(res) < 2:
            print(f"  {name:20s} too few terms (n={len(circ)}, {len(res)})")
            continue
        stat, pval = mannwhitneyu(circ, res, alternative="greater")
        print(
            f"  {name:20s} circ n={len(circ):2d} median={circ.median():.3f}  "
            f"resident n={len(res):2d} median={res.median():.3f}  U={stat:5.1f}  p={pval:.2e}"
        )

    # Abundance confound: does invariance simply track how many cells the model saw?
    both = pd.concat([specific, resolved])
    rho, pval = spearmanr(both["invariance"], np.log10(both["total_cells"]))
    print(f"\nSpearman(invariance, log10 total_cells) = {rho:+.3f}  p = {pval:.3f}")
    rho_n, p_n = spearmanr(both["invariance"], both["n_organs"])
    print(f"Spearman(invariance, n_organs)           = {rho_n:+.3f}  p = {p_n:.3f}")


if __name__ == "__main__":
    main()
