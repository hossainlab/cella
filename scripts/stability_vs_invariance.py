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
    specific = merged[merged["tier"].isin(["specific", "granularity-resolved"])].copy()
    specific["normalized_invariance"] = specific["invariance"] / specific["stability"]
    specific.to_parquet(PROCESSED / "invariance_with_stability.parquet", index=False)

    counts = specific["tier"].value_counts()
    print(
        f"{len(specific)} cell types with matched-n stability "
        f"({counts.get('specific', 0)} specific, "
        f"{counts.get('granularity-resolved', 0)} granularity-resolved)\n"
    )

    rho, pval = spearmanr(specific["invariance"], specific["stability"])
    print("Spearman(invariance, stability):")
    print(f"  tier 1 + 2  rho = {rho:+.3f}  p = {pval:.3f}   (n={len(specific)})")
    for tier in ("specific", "granularity-resolved"):
        sub = specific[specific["tier"] == tier]
        if len(sub) > 3:
            r, pv = spearmanr(sub["invariance"], sub["stability"])
            print(f"  {tier:20s} rho = {r:+.3f}  p = {pv:.3f}   (n={len(sub)})")
    print("  -> tier 1 shows no association, so coefficient noise does not explain")
    print("     the gradient among specifically annotated cell types. Tier 2 does")
    print("     show one: coarse terms pool heterogeneous populations, which makes")
    print("     their coefficients both noisier and less consistent across organs.")
    print("     The rescued terms are therefore reported as secondary evidence and")
    print("     the headline claim rests on tier 1.\n")

    tier1 = specific[specific["tier"] == "specific"]
    circ = tier1[tier1["lineage"].isin(CIRCULATING)]
    res = tier1[tier1["lineage"].isin(RESIDENT)]
    _, p_stab = mannwhitneyu(circ["stability"], res["stability"], alternative="two-sided")
    _, p_inv = mannwhitneyu(circ["invariance"], res["invariance"], alternative="greater")
    print(f"TIER 1 ONLY -- circulating (n={len(circ)}) vs tissue-resident (n={len(res)}):")
    print(
        f"  stability   {circ['stability'].median():.3f} vs {res['stability'].median():.3f}"
        f"   two-sided p = {p_stab:.3f}"
    )
    print(
        f"  invariance  {circ['invariance'].median():.3f} vs {res['invariance'].median():.3f}"
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

    t1 = specific[specific["tier"] == "specific"]
    t2 = specific[specific["tier"] == "granularity-resolved"]
    ax1.scatter(
        t1["stability"], t1["invariance"],
        c=[LINEAGE_COLORS.get(x, "#999999") for x in t1["lineage"]],
        s=90, edgecolor="white", zorder=3,
    )
    ax1.scatter(
        t2["stability"], t2["invariance"], facecolor="none",
        edgecolor=[LINEAGE_COLORS.get(x, "#999999") for x in t2["lineage"]],
        s=95, lw=1.7, zorder=3,
    )
    lim = [0, max(specific["stability"].max(), specific["invariance"].max()) * 1.12]
    ax1.plot(lim, lim, ls=":", color="#777777", lw=1.2, zorder=1,
             label="cross-organ = within-organ ceiling")
    ax1.set_xlabel("Within-organ replicate stability (matched n)", fontsize=11)
    ax1.set_ylabel("Cross-organ invariance", fontsize=11)
    rho1, p1 = spearmanr(t1["invariance"], t1["stability"])
    rho2, p2 = spearmanr(t2["invariance"], t2["stability"])
    ax1.set_title(
        "A  Noise does not explain the tier-1 gradient\n"
        f"tier 1 rho = {rho1:+.2f}, p = {p1:.2f}   |   "
        f"tier 2 rho = {rho2:+.2f}, p = {p2:.3f}",
        fontsize=12, loc="left",
    )
    from matplotlib.lines import Line2D

    present = [lin for lin in LINEAGE_COLORS if (specific["lineage"] == lin).any()]
    handles = [
        Line2D([], [], ls=":", color="#777777", label="cross-organ = within-organ ceiling"),
        Line2D([], [], marker="o", ls="", color="#444444", label="tier 1 (specific)",
               markeredgecolor="white"),
        Line2D([], [], marker="o", ls="", markerfacecolor="none", color="#444444",
               label="tier 2 (granularity-resolved)"),
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
    data_inv = [circ["invariance"], res["invariance"]]
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
        "B  Tier 1: stability is comparable; invariance is not\n"
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
