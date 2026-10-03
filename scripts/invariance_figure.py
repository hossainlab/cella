"""Figure for the cross-organ invariance analysis.

Panel A: every multi-organ, specifically-annotated cell type ranked by its mean
cross-organ cosine, against the mismatched-cell-type null band.
Panel B: the same scores grouped by broad lineage.

Run after scripts/invariance_analysis.py:
  uv run python scripts/invariance_figure.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import mannwhitneyu

PROCESSED = Path("data/processed")
OUT = Path("docs/images/cella_invariance.png")

LINEAGE_COLORS = {
    "Lymphoid": "#2166ac",
    "Erythroid/Mega": "#4393c3",
    "Myeloid": "#5aae61",
    "Epithelial": "#f4a582",
    "Endothelial": "#d6604d",
    "Mesenchymal/Stromal": "#b2182b",
    "Other": "#999999",
}
CIRCULATING = ["Lymphoid", "Erythroid/Mega", "Myeloid"]
RESIDENT = ["Epithelial", "Endothelial", "Mesenchymal/Stromal"]


def main() -> None:
    scores = pd.read_parquet(PROCESSED / "invariance_scores.parquet")
    pairs = pd.read_parquet(PROCESSED / "invariance_pairs.parquet")
    null = pairs.loc[~pairs["matched"], "cosine"]
    null_mu, null_sd = null.mean(), null.std()

    specific = scores[~scores["low_granularity"]].sort_values("mean_cosine")

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(15, 9), gridspec_kw={"width_ratios": [2.3, 1]}
    )

    # --- Panel A: ranked cell types -------------------------------------------
    y = range(len(specific))
    colors = [LINEAGE_COLORS.get(lin, "#999999") for lin in specific["lineage"]]
    ax_a.axvspan(
        null_mu - null_sd,
        null_mu + null_sd,
        color="#cccccc",
        alpha=0.55,
        zorder=0,
        label="null ±1 SD (mismatched cell types)",
    )
    ax_a.axvline(null_mu, color="#555555", ls="--", lw=1.2, zorder=1, label="null mean")
    ax_a.hlines(y, null_mu, specific["mean_cosine"], color=colors, lw=2.2, zorder=2)
    ax_a.scatter(specific["mean_cosine"], y, c=colors, s=70, zorder=3, edgecolor="white")
    labels = [
        f"{lab}  ({n})"
        for lab, n in zip(specific["ontology_label"], specific["n_organs"], strict=True)
    ]
    ax_a.set_yticks(list(y))
    ax_a.set_yticklabels(labels, fontsize=9)
    ax_a.set_xlabel("Mean cross-organ cosine of discriminative weights", fontsize=11)
    ax_a.set_title(
        "A  Organ-invariance of discriminative cell-type identity\n"
        f"{len(specific)} cell types annotated in ≥2 organs (organ count in parentheses)",
        fontsize=12,
        loc="left",
    )
    ax_a.legend(loc="lower right", fontsize=9, framealpha=0.95)
    ax_a.grid(axis="x", alpha=0.25)
    ax_a.set_axisbelow(True)

    # --- Panel B: by lineage ---------------------------------------------------
    # ascending: matplotlib draws the first group at the bottom, so the most
    # invariant lineage ends up on top, matching panel A.
    order = specific.groupby("lineage")["mean_cosine"].median().sort_values().index
    data = [specific.loc[specific["lineage"] == lin, "mean_cosine"].to_numpy() for lin in order]
    box = ax_b.boxplot(
        data, vert=False, widths=0.6, patch_artist=True, showfliers=False, zorder=2
    )
    for patch, lin in zip(box["boxes"], order, strict=False):
        patch.set_facecolor(LINEAGE_COLORS.get(lin, "#999999"))
        patch.set_alpha(0.55)
    for median in box["medians"]:
        median.set_color("#222222")
    for i, (lin, vals) in enumerate(zip(order, data, strict=False), start=1):
        ax_b.scatter(
            vals,
            [i] * len(vals),
            color=LINEAGE_COLORS.get(lin, "#999999"),
            s=42,
            zorder=3,
            edgecolor="white",
        )
    ax_b.axvline(null_mu, color="#555555", ls="--", lw=1.2, zorder=1)
    ax_b.set_yticklabels(
        [f"{lin}  (n={len(d)})" for lin, d in zip(order, data, strict=True)], fontsize=9
    )
    ax_b.set_xlabel("Mean cross-organ cosine", fontsize=11)

    circ = specific.loc[specific["lineage"].isin(CIRCULATING), "mean_cosine"]
    res = specific.loc[specific["lineage"].isin(RESIDENT), "mean_cosine"]
    _, pval = mannwhitneyu(circ, res, alternative="greater")
    ax_b.set_title(
        "B  Grouped by lineage\n"
        f"circulating (n={len(circ)}) > tissue-resident (n={len(res)}), "
        f"one-sided Mann–Whitney p = {pval:.1e}",
        fontsize=12,
        loc="left",
    )
    ax_b.grid(axis="x", alpha=0.25)
    ax_b.set_axisbelow(True)

    fig.suptitle(
        "Circulating lineages carry organ-invariant discriminative identity; "
        "tissue-resident lineages are organ-adapted",
        fontsize=13.5,
        y=0.985,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
