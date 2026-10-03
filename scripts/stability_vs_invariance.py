"""Does coefficient noise explain the cross-organ invariance gradient?

Joins per-cell-type replicate stability to the cross-organ invariance score and
tests the competing explanation: that tissue-resident cell types score low
across organs simply because their coefficients are less reproducible.

Writes data/processed/invariance_with_stability.parquet and
docs/images/cella_stability.png.

Run after scripts/invariance_analysis.py and scripts/stability_analysis.py.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

PROCESSED = Path("data/processed")
OUT = Path("docs/images/cella_stability.png")

CIRCULATING = ["Lymphoid", "Erythroid/Mega", "Myeloid"]
RESIDENT = ["Epithelial", "Endothelial", "Mesenchymal/Stromal"]
LINEAGE_COLORS = {
    "Lymphoid": "#2166ac",
    "Erythroid/Mega": "#4393c3",
    "Myeloid": "#5aae61",
    "Epithelial": "#f4a582",
    "Endothelial": "#d6604d",
    "Mesenchymal/Stromal": "#b2182b",
    "Other": "#999999",
}


def main() -> None:
    scores = pd.read_parquet(PROCESSED / "invariance_scores.parquet")
    stab = pd.read_parquet(PROCESSED / "stability_cell_type_organ.parquet")

    scored = stab[stab["eligible"] & stab["cl_id"].notna()]
    per_cl = (
        scored.groupby("cl_id")
        .agg(
            stability=("stability", "mean"),
            n_organs_scored=("organ", "nunique"),
            cosine_vs_published=("cosine_vs_published", "mean"),
        )
        .reset_index()
    )

    merged = scores.merge(per_cl, on="cl_id", how="inner")
    specific = merged[~merged["low_granularity"]].copy()
    specific["normalized_invariance"] = specific["mean_cosine"] / specific["stability"]
    specific.to_parquet(PROCESSED / "invariance_with_stability.parquet", index=False)

    print(f"{len(specific)} specific cell types with matched-n stability\n")

    rho, pval = spearmanr(specific["mean_cosine"], specific["stability"])
    print(f"Spearman(invariance, stability) = {rho:+.3f}  p = {pval:.3f}")
    print("  -> if ~0, coefficient noise does not explain the invariance gradient\n")

    circ = specific[specific["lineage"].isin(CIRCULATING)]
    res = specific[specific["lineage"].isin(RESIDENT)]
    _, p_stab = mannwhitneyu(circ["stability"], res["stability"], alternative="two-sided")
    _, p_inv = mannwhitneyu(circ["mean_cosine"], res["mean_cosine"], alternative="greater")
    print(f"circulating (n={len(circ)}) vs tissue-resident (n={len(res)}):")
    print(
        f"  stability   {circ['stability'].median():.3f} vs {res['stability'].median():.3f}"
        f"   two-sided p = {p_stab:.3f}"
    )
    print(
        f"  invariance  {circ['mean_cosine'].median():.3f} vs {res['mean_cosine'].median():.3f}"
        f"   one-sided p = {p_inv:.2e}"
    )

    _, p_norm = mannwhitneyu(
        circ["normalized_invariance"], res["normalized_invariance"], alternative="greater"
    )
    print(
        f"  invariance/stability  {circ['normalized_invariance'].median():.3f} vs "
        f"{res['normalized_invariance'].median():.3f}   one-sided p = {p_norm:.2e}"
    )

    # --- figure ---------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
    colors = [LINEAGE_COLORS.get(x, "#999999") for x in specific["lineage"]]

    ax1.scatter(
        specific["stability"], specific["mean_cosine"], c=colors, s=90,
        edgecolor="white", zorder=3,
    )
    lim = [0, max(specific["stability"].max(), specific["mean_cosine"].max()) * 1.12]
    ax1.plot(lim, lim, ls=":", color="#777777", lw=1.2, zorder=1,
             label="cross-organ = within-organ ceiling")
    ax1.set_xlabel("Within-organ replicate stability (matched n)", fontsize=11)
    ax1.set_ylabel("Cross-organ invariance (mean cosine)", fontsize=11)
    ax1.set_title(
        f"A  Noise does not explain the gradient\nSpearman rho = {rho:+.2f}, p = {pval:.2f}",
        fontsize=12, loc="left",
    )
    from matplotlib.lines import Line2D

    present = [lin for lin in LINEAGE_COLORS if (specific["lineage"] == lin).any()]
    handles = [
        Line2D([], [], ls=":", color="#777777", label="cross-organ = within-organ ceiling")
    ] + [
        Line2D([], [], marker="o", ls="", color=LINEAGE_COLORS[lin], label=lin,
               markeredgecolor="white")
        for lin in present
    ]
    ax1.legend(handles=handles, fontsize=8, loc="upper left", framealpha=0.95)
    ax1.grid(alpha=0.25)
    ax1.set_axisbelow(True)

    groups = ["circulating", "tissue-resident"]
    data_stab = [circ["stability"], res["stability"]]
    data_inv = [circ["mean_cosine"], res["mean_cosine"]]
    x = np.arange(2)
    for offset, data, lab, col in [
        (-0.17, data_stab, "within-organ stability", "#999999"),
        (0.17, data_inv, "cross-organ invariance", "#2166ac"),
    ]:
        parts = ax2.boxplot(
            data, positions=x + offset, widths=0.3, patch_artist=True, showfliers=False
        )
        for patch in parts["boxes"]:
            patch.set_facecolor(col)
            patch.set_alpha(0.5)
        for med in parts["medians"]:
            med.set_color("#222222")
        for i, vals in enumerate(data):
            jitter = np.random.default_rng(0).normal(0, 0.03, len(vals))
            ax2.scatter(
                np.full(len(vals), x[i] + offset) + jitter,
                vals, color=col, s=36, zorder=3, edgecolor="white",
                label=lab if i == 0 else None,
            )
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        [f"{g}\n(n={len(d)})" for g, d in zip(groups, data_stab, strict=True)]
    )
    ax2.set_ylabel("Cosine", fontsize=11)
    ax2.set_title(
        "B  Stability is comparable; invariance is not\n"
        f"stability p = {p_stab:.2f} (n.s.)   invariance p = {p_inv:.1e}",
        fontsize=12, loc="left",
    )
    ax2.legend(fontsize=9, loc="upper right")
    ax2.grid(axis="y", alpha=0.25)
    ax2.set_axisbelow(True)

    fig.suptitle(
        "Tissue-resident cell types are no less reproducible - "
        "their identity genuinely differs between organs",
        fontsize=13, y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
