"""Figures and reported numbers for the Cella preprint.

Every quantity cited in the manuscript is computed here from the project's
artifacts and written to ``preprint/numbers.tex`` as a LaTeX macro, so the text
cannot drift from the data. Run from the repository root:

    uv run --group analysis python preprint/scripts/make_figures.py

Inputs: data/processed/ (artifacts, benchmark results), data/external/enrichr/
(downloaded by scripts/lookup_benchmark.py) and web/public/data/ (written by
`cella export`).
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest, mannwhitneyu, spearmanr, wilcoxon
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "preprint"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# Reference categorical palette (dataviz skill), validated for the light surface;
# slots 3-4 sit below 3:1 contrast, so every series also gets a marker shape and
# a direct label.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MARKERS = ["o", "s", "^", "D"]
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#a9a8a2"
GRID = "#e6e5e0"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    }
)

NUM: dict[str, str] = {}


def num(name: str, value: object, fmt: str | None = None) -> None:
    """Record a number for numbers.tex (macro \\name)."""
    if fmt is not None:
        value = format(value, fmt)
    NUM[name] = str(value)


def pfmt(p: float) -> str:
    """P-value as LaTeX: 2 significant digits, scientific below 1e-3."""
    if p < 1e-3:
        mant, exp = f"{p:.1e}".split("e")
        return f"{mant}\\times10^{{{int(exp)}}}"
    return f"{p:.2g}"


def pct(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}\\%"


def panel_label(ax, letter: str) -> None:
    ax.text(-0.12, 1.04, letter, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom")


# ----------------------------------------------------------------- resource


def resource_numbers() -> None:
    organs = pd.read_parquet(PROC / "organs.parquet")
    cto = pd.read_parquet(PROC / "cell_type_organ.parquet")
    reg = pd.read_parquet(PROC / "registry.parquet")
    datasets = {d.strip() for s in organs["datasets_list"] for d in s.split("|") if d.strip()}
    num("nOrgans", len(organs))
    num("nCells", f"{organs['n_cells'].sum() / 1e6:.2f}")
    num("nDatasets", len(datasets))
    num("nLabels", len(cto))
    num("nCLTerms", len(reg))
    num("nMultiOrganTerms", int((reg["n_organs"] >= 2).sum()))
    genes = []
    for organ in organs["organ"]:
        w = pd.read_parquet(PROC / "weights" / f"{organ.replace(' ', '_')}.parquet")
        genes.append(w.shape[1])
    num("minModelGenes", f"{min(genes):,}".replace(",", "{,}"))
    num("maxModelGenes", f"{max(genes):,}".replace(",", "{,}"))

    data = ROOT / "web" / "public" / "data"
    files = [p for p in data.rglob("*.json") if "expr" not in p.parts]
    num("nExportFiles", f"{len(files):,}".replace(",", "{,}"))
    pct_mb = sum(p.stat().st_size for p in (data / "expr").glob("*.pct.bin.gz")) / 1e6
    mean_mb = sum(p.stat().st_size for p in (data / "expr").glob("*.mean.bin.gz")) / 1e6
    num("exportPctMB", f"{pct_mb:.1f}")
    num("exportMeanMB", f"{mean_mb:.1f}")
    num("exportJsonMB", f"{sum(p.stat().st_size for p in files) / 1e6:.1f}")


# --------------------------------------------------------- marker gating (Fig 2)


def figure_gating() -> None:
    from cella.core.config import ORGANS
    from cella.pipeline.emit import select_markers

    rows = []
    examples = {
        ("Lung", "Goblet cells"),
        ("Heart", "Adipocytes"),
        ("Blood", "Age-associated B cells"),
        ("Lung", "Alveolar macrophages"),
    }
    example_rows = []
    for organ in ORGANS:
        slug = organ.replace(" ", "_")
        w = pd.read_parquet(PROC / "weights" / f"{slug}.parquet")
        p = pd.read_parquet(PROC / "expression" / f"{slug}__pct.parquet").reindex(columns=w.columns)
        p = p.fillna(0.0)
        for ct, coef in w.iterrows():
            pin = p.loc[ct]
            pout = p.drop(index=ct).max()
            raw = select_markers(coef, pin, pout, top_n=25, min_pct=0.0)["positive"]
            gated = select_markers(coef, pin, pout, top_n=25, min_pct=0.1)["positive"]
            low = (pin.reindex(raw.index) < 0.1).to_numpy()
            rows.append(
                {
                    "organ": organ,
                    "cell_type": ct,
                    "frac25": low.mean(),
                    "frac5": low[:5].mean(),
                    "n_cells_pct": None,
                }
            )
            canon = {("Lung", "Goblet cells"): ("MUC5AC", "Goblet"), ("Heart", "Adipocytes"): ("PPARG", "Adipo")}
            if (organ, ct) in canon:
                gname, key = canon[(organ, ct)]
                num(f"gate{key}GatedRank", list(gated.index).index(gname) + 1)
                num(f"gate{key}RawRank", int(coef.rank(ascending=False, method="min")[gname]))
            if (organ, ct) in examples:
                example_rows.append((organ, ct, list(raw.index[:6]), list(gated.index[:6]), pin))
    df = pd.DataFrame(rows)
    num("gateFracAll", pct(df["frac25"].mean()))
    num("gateFracTopFive", pct(df["frac5"].mean()))
    num("gateMajority", int((df["frac25"] > 0.5).sum()))
    num("gateNTypes", len(df))

    cto = pd.read_parquet(PROC / "cell_type_organ.parquet")
    df = df.merge(
        cto[["organ", "curated_label", "cell_count"]],
        left_on=["organ", "cell_type"],
        right_on=["organ", "curated_label"],
        how="left",
    )
    rho, pval = spearmanr(np.log10(df["cell_count"]), df["frac25"])
    num("gateRho", f"{rho:.2f}")
    num("gateRhoP", pfmt(pval))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax1.hist(df["frac25"], bins=np.linspace(0, 1, 21), color=SLOTS[0], edgecolor="white", linewidth=0.8)
    ax1.set_xlabel("Fraction of raw top-25 markers expressed\nin <10% of the cell type's own cells")
    ax1.set_ylabel("Cell types (organ-specific labels)")
    ax1.axvline(0.5, color=INK2, lw=0.8, ls="--")
    ax1.text(0.52, ax1.get_ylim()[1] * 0.92, f"{(df['frac25'] > 0.5).sum()} of {len(df)}\nabove half",
             fontsize=7, color=INK2, va="top")
    ax1.grid(axis="x", visible=False)
    panel_label(ax1, "a")

    ax2.scatter(df["cell_count"], df["frac25"], s=9, color=SLOTS[0], alpha=0.55, linewidths=0)
    ax2.set_xscale("log")
    ax2.set_xlabel("Cells of the label in the atlas (log scale)")
    ax2.set_ylabel("Fraction of raw top-25 markers\nbelow 10% prevalence")
    ax2.set_title(f"Spearman ρ = {rho:.2f}", fontsize=8, color=INK2, loc="left")
    panel_label(ax2, "b")
    fig.tight_layout()
    fig.savefig(FIG / "fig2_gating.pdf")
    plt.close(fig)

    # LaTeX table of examples (before vs after gating).
    lines = []
    order = [("Lung", "Goblet cells"), ("Heart", "Adipocytes"), ("Blood", "Age-associated B cells"),
             ("Lung", "Alveolar macrophages")]
    ex = {(o, c): (r, g, pin) for o, c, r, g, pin in example_rows}
    for o, c in order:
        r, g, pin = ex[(o, c)]
        def fmt(genes: list[str], mark: bool) -> str:
            out = []
            for gname in genes:
                tok = f"\\textit{{{gname}}}"
                if mark and pin.get(gname, 0.0) < 0.1:
                    tok = f"\\textcolor{{lowprev}}{{{tok}}}"
                out.append(tok)
            return ", ".join(out)
        lines.append(f"{o} & {c} & {fmt(r, True)} & {fmt(g, False)} \\\\")
    (OUT / "table_gating_examples.tex").write_text("\n".join(lines) + "\n")


# ------------------------------------------------------ reverse lookup (Fig 3)

LOOKUP_NAMES = {
    "expr_pct": "Mean fraction expressing (Cella)",
    "hypergeom": "Hypergeometric overlap, gated markers",
    "hybrid": "Hybrid: weights + expression",
    "expr_spec": "Mean expression z-score",
    "weight_genez_gated": "Per-gene z-scored weights, gated",
    "weight_gated": "Mean classifier weight, gated",
    "weight_genez": "Per-gene z-scored weights",
    "weight_mean": "Mean classifier weight",
    "clf_pseudocell": "Classifier on a pseudo-cell",
}


def boot_ci(x: np.ndarray, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def figure_lookup() -> None:
    from cella.analysis.lookup_benchmark import (
        DEV_LIBRARY,
        build_index,
        confidence_calibration,
        load_queries,
    )

    queries, acc = load_queries()
    num("lkTerms", f"{int(acc['terms'].sum()):,}".replace(",", "{,}"))
    num("lkResolved", int(acc["resolved"].sum()))

    full = pd.read_parquet(PROC / "benchmark_lookup.parquet")
    full["split"] = np.where(full["library"] == DEV_LIBRARY, "dev", "test")
    num("lkScored", full["term"].nunique())
    num("lkIndependent", full.loc[full["stratum"] == "independent", "term"].nunique())
    num("lkOverlap", full.loc[full["stratum"] == "overlap", "term"].nunique())
    ind = full[full["stratum"] == "independent"]
    test = ind[ind["split"] == "test"]
    dev = ind[ind["split"] == "dev"]
    num("lkTest", test["term"].nunique())
    num("lkDev", dev["term"].nunique())

    stats = {}
    for m, g in test.groupby("method"):
        top1 = (g["rank_relaxed"] <= 1).to_numpy(float)
        top5 = (g["rank_relaxed"] <= 5).to_numpy(float)
        stats[m] = {
            "top1": top1.mean(),
            "top1_ci": boot_ci(top1),
            "top5": top5.mean(),
            "top5_ci": boot_ci(top5, seed=1),
            "mrr": (1 / g["rank_relaxed"]).mean(),
        }
    for m, key in [("expr_pct", "Expr"), ("weight_mean", "Wmean"), ("weight_gated", "Wgated"),
                   ("hybrid", "Hybrid"), ("hypergeom", "Hyper"), ("clf_pseudocell", "Pseudo"),
                   ("weight_genez_gated", "Wgenez")]:
        num(f"lk{key}TopOne", pct(stats[m]["top1"]))
        num(f"lk{key}TopFive", pct(stats[m]["top5"]))
    lo, hi = stats["expr_pct"]["top1_ci"]
    num("lkExprTopOneCI", f"{100 * lo:.0f}--{100 * hi:.0f}\\%")
    lo, hi = stats["weight_mean"]["top1_ci"]
    num("lkWmeanTopOneCI", f"{100 * lo:.0f}--{100 * hi:.0f}\\%")

    # Paired exact McNemar test on top-1 correctness, expression vs mean weight.
    piv = test.pivot_table(index="term", columns="method", values="rank_relaxed")
    a = piv["expr_pct"] <= 1
    b = piv["weight_mean"] <= 1
    n01, n10 = int((~a & b).sum()), int((a & ~b).sum())
    num("lkMcNemarP", pfmt(binomtest(n10, n10 + n01, 0.5).pvalue))
    num("lkDisc", f"{n10}")
    num("lkDiscRev", f"{n01}")
    # Expression against the next-best rules: is its lead over them significant?
    for other, key in [("hypergeom", "Hyper"), ("hybrid", "Hybrid")]:
        b = piv[other] <= 1
        m10, m01 = int((a & ~b).sum()), int((~a & b).sum())
        num(f"lk{key}Disc", m10)
        num(f"lk{key}DiscRev", m01)
        num(f"lk{key}McNemarP", pfmt(binomtest(m10, m10 + m01, 0.5).pvalue))

    # Per-library top-1 (independent queries), to show where each rule wins.
    lib = ind.groupby(["library", "method"])["rank_relaxed"].apply(lambda r: (r <= 1).mean()).unstack()
    libkey = {"Tabula_Sapiens": "TS", "Azimuth_2023": "Az", "PanglaoDB_Augmented_2021": "Pg",
              "CellMarker_2024": "CM"}
    for lname, key in libkey.items():
        num(f"lk{key}N", ind.loc[ind["library"] == lname, "term"].nunique())
        for m, mk in [("expr_pct", "Expr"), ("hypergeom", "Hyper"), ("weight_mean", "Wmean")]:
            num(f"lk{key}{mk}TopOne", pct(lib.loc[lname, m]))
    num("lkLibExprGtWmean", int((lib["expr_pct"] > lib["weight_mean"]).sum()))
    num("lkLibHyperGtExpr", int((lib["hypergeom"] > lib["expr_pct"]).sum()))

    # Development-library metrics of the leading rules.
    def dev_metric(m: str, f) -> float:
        return f(dev[dev["method"] == m]["rank_relaxed"])
    for m, key in [("expr_pct", "Expr"), ("hypergeom", "Hyper"), ("expr_spec", "Espec")]:
        num(f"lkDev{key}TopOneX", pct(dev_metric(m, lambda r: (r <= 1).mean())))
        num(f"lkDev{key}TopFive", pct(dev_metric(m, lambda r: (r <= 5).mean())))
        num(f"lkDev{key}MRR", f"{dev_metric(m, lambda r: (1 / r).mean()):.2f}")

    # Dev library numbers (selection set).
    num("lkDevExprTopOne", pct((dev[dev["method"] == "expr_pct"]["rank_relaxed"] <= 1).mean()))
    num("lkDevWmeanTopOne", pct((dev[dev["method"] == "weight_mean"]["rank_relaxed"] <= 1).mean()))

    # Overlap stratum (sanity: same ordering).
    ov = full[full["stratum"] == "overlap"]
    num("lkOvExprTopOne", pct((ov[ov["method"] == "expr_pct"]["rank_relaxed"] <= 1).mean()))
    num("lkOvWmeanTopOne", pct((ov[ov["method"] == "weight_mean"]["rank_relaxed"] <= 1).mean()))

    sub = pd.read_parquet(PROC / "benchmark_lookup_subsample.parquet")
    sub = sub[sub["stratum"] == "independent"]
    subsum = sub.groupby(["k", "method"])["rank_relaxed"].apply(lambda r: (r <= 1).mean()).unstack()
    for k in (3, 5, 10):
        num(f"lkSub{['', '', '', 'Three', '', 'Five', '', '', '', '', 'Ten'][k]}Expr", pct(subsum.loc[k, "expr_pct"]))
        num(f"lkSub{['', '', '', 'Three', '', 'Five', '', '', '', '', 'Ten'][k]}Wmean", pct(subsum.loc[k, "weight_mean"]))

    cal = confidence_calibration(queries, build_index())
    row = cal[(cal["min_margin"] == 0.10) & (cal["split"] == "test")].iloc[0]
    num("calConfFrac", pct(row["confident_frac"]))
    num("calPrecConf", f"{row['precision_confident']:.2f}")
    num("calPrecRest", f"{row['precision_rest']:.2f}")
    n_conf = round(row["confident_frac"] * row["n"])
    n_rest = int(row["n"]) - n_conf
    for key, prec, n in [("Conf", row["precision_confident"], n_conf), ("Rest", row["precision_rest"], n_rest)]:
        lo, hi = proportion_confint(round(prec * n), n, method="wilson")
        num(f"calPrec{key}CI", f"{lo:.2f}--{hi:.2f}")
        num(f"calN{key}", n)
    margins = cal[cal["split"] == "dev"].sort_values("min_margin")
    num("calMarginMin", f"{margins['min_margin'].min():.2f}")
    num("calMarginMax", f"{margins['min_margin'].max():.2f}")
    drow = cal[(cal["min_margin"] == 0.10) & (cal["split"] == "dev")].iloc[0]
    num("calDevPrecConf", f"{drow['precision_confident']:.2f}")
    cal.to_csv(OUT / "supplementary_calibration.csv", index=False)

    # ---- figure
    order = sorted(stats, key=lambda m: stats[m]["top1"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [1.45, 1]})
    y = np.arange(len(order))
    for i, m in enumerate(order):
        chosen = m == "expr_pct"
        col = SLOTS[0] if chosen else MUTED
        s = stats[m]
        ax1.plot([s["top1"], s["top5"]], [i, i], color=col, lw=1.2, zorder=2)
        ax1.errorbar(s["top1"], i, xerr=[[s["top1"] - s["top1_ci"][0]], [s["top1_ci"][1] - s["top1"]]],
                     fmt="o", ms=5, color=col, ecolor=col, elinewidth=0.8, capsize=0, zorder=3)
        ax1.plot(s["top5"], i, marker="D", ms=4.5, mfc="white", mec=col, mew=1.2, ls="none", zorder=3)
    ax1.set_yticks(y)
    ax1.set_yticklabels([LOOKUP_NAMES[m] for m in order])
    for lab, m in zip(ax1.get_yticklabels(), order, strict=True):
        if m == "expr_pct":
            lab.set_fontweight("bold")
    ax1.set_xlim(0, 0.85)
    ax1.set_xlabel(f"Fraction of held-out queries (n = {test['term'].nunique()})")
    ax1.grid(axis="y", visible=False)
    ax1.plot([], [], "o", color=INK2, ms=5, label="top-1 (95% bootstrap CI)")
    ax1.plot([], [], "D", mfc="white", mec=INK2, ms=4.5, label="top-5")
    ax1.legend(loc="center right", fontsize=7)
    panel_label(ax1, "a")

    show = ["expr_pct", "hybrid", "weight_genez_gated", "weight_mean"]
    ks = [3, 5, 10]
    for j, m in enumerate(show):
        vals = [subsum.loc[k, m] for k in ks]
        ax2.plot(ks, vals, color=SLOTS[j], marker=MARKERS[j], ms=4.5, lw=1.5)
        ax2.text(10.4, vals[-1], LOOKUP_NAMES[m].replace(" (Cella)", ""), color=INK, fontsize=6.5,
                 va="center")
    ax2.set_xticks(ks)
    ax2.set_xlim(2.5, 10.2)
    ax2.set_ylim(0, 0.45)
    ax2.set_xlabel("Genes pasted per query (random subsets)")
    ax2.set_ylabel("Top-1 accuracy")
    panel_label(ax2, "b")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_lookup.pdf")
    plt.close(fig)

    # Supplementary table: all methods, dev and test.
    rows = []
    for split, g in ind.groupby("split"):
        for m, h in g.groupby("method"):
            rows.append({"split": split, "method": LOOKUP_NAMES[m],
                         "top1": (h["rank_relaxed"] <= 1).mean(), "top3": (h["rank_relaxed"] <= 3).mean(),
                         "top5": (h["rank_relaxed"] <= 5).mean(), "mrr": (1 / h["rank_relaxed"]).mean(),
                         "n": h["term"].nunique()})
    pd.DataFrame(rows).to_csv(OUT / "supplementary_lookup.csv", index=False)
    lines = []
    for m in sorted(stats, key=lambda m: -stats[m]["top1"]):
        d = ind[(ind["method"] == m) & (ind["split"] == "dev")]
        s = stats[m]
        lines.append(
            f"{LOOKUP_NAMES[m]} & {(d['rank_relaxed'] <= 1).mean():.2f} & {(d['rank_relaxed'] <= 5).mean():.2f} & "
            f"{(1 / d['rank_relaxed']).mean():.2f} & {s['top1']:.2f} & {s['top5']:.2f} & {s['mrr']:.2f} \\\\"
        )
    (OUT / "table_lookup.tex").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------- marker panels (Fig 4)

PANEL_NAMES = {
    "coef_gated": "Coefficients, gated (Cella)",
    "de_wilcoxon": "Wilcoxon DE",
    "de_logfc": "log fold change, gated",
    "coef_raw": "Coefficients, raw",
}


def figure_panels() -> None:
    res = pd.concat(
        pd.read_parquet(f) for f in sorted((PROC / "benchmark_panels").glob("*.parquet")) if "__" not in f.name
    )
    num("pnSplits", res.groupby(["organ", "held_out"]).ngroups)
    num("pnOrgans", res["organ"].nunique())

    def paired(metric: str, k: int, other: str) -> tuple[float, int, int, float]:
        p = res[res["k"] == k].pivot_table(index=["organ", "held_out"], columns="method", values=metric)
        d = p["coef_gated"] - p[other]
        return float(d.mean()), int((d > 0).sum()), len(d), float(wilcoxon(d).pvalue)

    tests = []
    for metric, mk in [("marker_f1", "M"), ("lr_f1", "L")]:
        for k in (3, 5, 10, 20):
            for other, ok in [("coef_raw", "Raw"), ("de_wilcoxon", "Wilc"), ("de_logfc", "Lfc")]:
                d, wins, n, p = paired(metric, k, other)
                kk = {3: "Three", 5: "Five", 10: "Ten", 20: "Twenty"}[k]
                num(f"pn{mk}{kk}{ok}Diff", f"{d:+.3f}")
                num(f"pn{mk}{kk}{ok}Wins", f"{wins}/{n}")
                num(f"pn{mk}{kk}{ok}P", pfmt(p))
                tests.append((f"pn{mk}{kk}{ok}PHolm", p))
    # Holm correction over every paired comparison reported (2 readouts x 4 k x 3 methods).
    holm = multipletests([p for _, p in tests], method="holm")[1]
    for (name, _), ph in zip(tests, holm, strict=True):
        num(name, pfmt(ph))
    num("pnNTests", len(tests))
    adj = {name: ph for (name, _), ph in zip(tests, holm, strict=True)}
    num("pnRawMaxPHolm", pfmt(max(v for n, v in adj.items() if "Raw" in n)))
    num("pnMWilcOtherMinPHolm", pfmt(min(adj[f"pnM{k}WilcPHolm"] for k in ("Three", "Five", "Ten"))))
    pv = res[res["k"] == 10].pivot_table(index=["organ", "held_out"], columns="method", values="marker_f1")
    by_organ = (pv["coef_gated"] - pv["de_wilcoxon"]).groupby(level="organ").mean()
    num("pnWilcOrgansBetter", int((by_organ < 0).sum()))
    per_organ = res.groupby("organ")["held_out"].nunique()
    num("pnSplitsPerOrgan", f"{per_organ.min()}" if per_organ.min() == per_organ.max()
        else f"{per_organ.min()}--{per_organ.max()}")
    size = res[res["k"] == 10].groupby("method")["panel_size"].mean()
    num("pnSizeGated", f"{size['coef_gated']:.0f}")
    num("pnSizeWilc", f"{size['de_wilcoxon']:.0f}")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=False)
    methods = ["coef_gated", "de_wilcoxon", "de_logfc", "coef_raw"]
    # Points are dodged sideways (multiplicatively, on the log-k axis) so the
    # 95% intervals of converging methods stay readable.
    dodge = {m: f for m, f in zip(methods, [0.955, 0.985, 1.015, 1.045], strict=True)}
    for ax, metric, title, letter in [
        (axes[0], "marker_f1", "Marker lists only (no classifier)", "a"),
        (axes[1], "lr_f1", "Classifier trained on the panel", "b"),
    ]:
        for j, m in enumerate(methods):
            g = res[res["method"] == m].groupby("k")[metric]
            mean, sem = g.mean(), g.sem()
            ax.errorbar(mean.index * dodge[m], mean.values, yerr=1.96 * sem.values, color=SLOTS[j],
                        marker=MARKERS[j], ms=4.5, lw=1.5, elinewidth=0.7, capsize=0,
                        label=PANEL_NAMES[m])
        ax.set_xscale("log", base=2)
        ax.set_xticks([3, 5, 10, 20])
        ax.set_xticklabels(["3", "5", "10", "20"])
        ax.set_xlim(2.7, 22)
        ax.set_xlabel("Markers per cell type (k)")
        ax.set_ylabel("Macro-F1 on held-out dataset")
        ax.set_title(title, loc="left", color=INK2)
        panel_label(ax, letter)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=3)
    fig.savefig(FIG / "fig4_panels.pdf")
    plt.close(fig)


# ---------------------------------------------------------- invariance (Fig 5)


def invariance_numbers() -> None:
    s = pd.read_parquet(PROC / "invariance_scores.parquet")
    pairs = pd.read_parquet(PROC / "invariance_pairs.parquet")
    circ_l = ["Lymphoid", "Erythroid/Mega", "Myeloid"]
    res_l = ["Epithelial", "Endothelial", "Mesenchymal/Stromal"]
    t1 = s[s["tier"] == "specific"]
    num("invMulti", len(s))
    num("invTierOne", len(t1))
    num("invTierTwo", int((s["tier"] == "granularity-resolved").sum()))
    num("invNExcluded", int((s["tier"] == "excluded").sum()))

    def test(col: str, frame: pd.DataFrame) -> tuple[int, int, float, float, float]:
        c = frame.loc[frame["lineage"].isin(circ_l), col].dropna()
        r = frame.loc[frame["lineage"].isin(res_l), col].dropna()
        return len(c), len(r), c.median(), r.median(), mannwhitneyu(c, r, alternative="two-sided").pvalue

    nc, nr, mc, mr, p = test("invariance", t1)
    num("invRawP", pfmt(p))
    nc, nr, mc, mr, p = test("invariance_calibrated", t1)
    num("invNCirc", nc)
    num("invNRes", nr)
    num("invCalCirc", f"{mc:.3f}")
    num("invCalRes", f"{mr:.3f}")
    num("invCalP", pfmt(p))
    nc, nr, mc, mr, p = test("invariance_peripheral", t1)
    num("invPerNCirc", nc)
    num("invPerP", pfmt(p))

    from cella.analysis.invariance import calibrate_pairs

    sig = calibrate_pairs(pairs)
    lym = {"Blood", "Bone marrow", "Spleen", "Lymph node"}
    # One row per organ pair, so each pair counts once in the averages below.
    per_pair = sig.drop_duplicates(["organ_a", "organ_b"])
    n = per_pair["organ_a"].isin(lym).astype(int) + per_pair["organ_b"].isin(lym).astype(int)
    null_by = per_pair.groupby(n)["null_mean"].mean()
    num("invNPairsLL", int((n == 2).sum()))
    num("invNPairsPP", int((n == 0).sum()))
    num("invNullLL", f"{null_by.loc[2]:.3f}")
    num("invNullPP", f"{null_by.loc[0]:.3f}")
    null_sd = per_pair["null_sd"]
    num("invNullSD", f"{null_sd.median():.3f}")
    num("invNullSDRange", f"{null_sd.min():.2f}--{null_sd.max():.2f}")
    figure_invariance(s, float(null_sd.median()))

    # Sensitivity: drop haematopoietic terms that are tissue-resident rather than circulating.
    resident_immune = ["mast cell", "conventional dendritic cell"]
    nc, nr, mc, mr, p = test("invariance_calibrated", t1[~t1["ontology_label"].isin(resident_immune)])
    num("invSensNHaem", nc)
    num("invSensP", pfmt(p))

    rho, p = spearmanr(t1["invariance_calibrated"], np.log10(t1["total_cells"]))
    num("invRhoCells", f"{rho:+.2f}")
    num("invRhoCellsP", f"{p:.2f}")
    st = pd.read_parquet(PROC / "invariance_with_stability.parquet")
    st = st[(st["tier"] == "specific") & st["stability"].notna()]
    num("invNStab", len(st))
    rho, p = spearmanr(st["invariance_calibrated"], st["stability"])
    num("invRhoStab", f"{rho:+.2f}")
    num("invRhoStabP", f"{p:.2f}")


LINEAGE_ORDER = ["Erythroid/Mega", "Lymphoid", "Myeloid", "Epithelial", "Endothelial",
                 "Mesenchymal/Stromal"]


def figure_invariance(s: pd.DataFrame, sd: float) -> None:
    """Print-sized invariance figure: calibrated score per term, then by lineage.

    Haematopoietic lineages use the blue slot and structural (non-haematopoietic)
    ones the orange slot; the lineage itself is named on the axis, so colour only groups.
    """
    circ = {"Lymphoid", "Erythroid/Mega", "Myeloid"}
    t1 = s[s["tier"] == "specific"].sort_values("invariance_calibrated")
    t2 = s[s["tier"] == "granularity-resolved"]
    col = lambda lin: SLOTS[0] if lin in circ else SLOTS[1]  # noqa: E731

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 4.6), gridspec_kw={"width_ratios": [1.5, 1]})
    y = np.arange(len(t1))
    ax1.axvspan(-sd, sd, color=GRID, zorder=0)
    ax1.axvline(0, color=INK2, lw=0.7, ls="--", zorder=1)
    cs = [col(lin) for lin in t1["lineage"]]
    ax1.hlines(y, 0, t1["invariance_calibrated"], color=cs, lw=1.3, zorder=2)
    ax1.scatter(t1["invariance_calibrated"], y, color=cs, s=16, zorder=3, linewidths=0)
    labels = [f"{lab.replace(', human', '')} ({n})" for lab, n in zip(t1["ontology_label"], t1["n_organs"], strict=True)]
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=6)
    ax1.set_xlabel("Calibrated invariance\n(cosine above the organ pair's null)")
    ax1.grid(axis="y", visible=False)
    ax1.set_ylim(-0.8, len(t1) - 0.2)
    panel_label(ax1, "a")
    ax1.plot([], [], "o", color=SLOTS[0], ms=4, label="haematopoietic lineage")
    ax1.plot([], [], "o", color=SLOTS[1], ms=4, label="structural lineage")
    ax1.plot([], [], "s", color=GRID, ms=7, label="median null \u00b1 1 SD")

    lins = [lin for lin in LINEAGE_ORDER if (t1["lineage"] == lin).any()]
    rng = np.random.default_rng(0)
    for i, lin in enumerate(lins):
        v = t1.loc[t1["lineage"] == lin, "invariance_calibrated"].to_numpy()
        jit = rng.uniform(-0.12, 0.12, len(v))
        ax2.scatter(v, i + jit, color=col(lin), s=18, linewidths=0, zorder=3)
        ax2.plot([np.median(v)] * 2, [i - 0.3, i + 0.3], color=INK, lw=1.4, zorder=4)
        w = t2.loc[t2["lineage"] == lin, "invariance_calibrated"].to_numpy()
        if len(w):
            ax2.scatter(w, i + rng.uniform(-0.12, 0.12, len(w)), facecolor="white", edgecolor=col(lin),
                        s=18, lw=1.0, zorder=3)
    ax2.axvline(0, color=INK2, lw=0.7, ls="--")
    ax2.set_yticks(range(len(lins)))
    ax2.set_yticklabels([f"{lin} (n={int((t1['lineage'] == lin).sum())})" for lin in lins], fontsize=7)
    ax2.invert_yaxis()
    ax2.set_xlabel("Calibrated invariance")
    ax2.grid(axis="y", visible=False)
    ax2.scatter([], [], color=INK2, s=14, label="specific term")
    ax2.scatter([], [], facecolor="white", edgecolor=INK2, s=14, label="coarse term, comparable organs")
    ax2.plot([], [], color=INK, lw=1.4, label="median (specific)")
    panel_label(ax2, "b")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.07, 1, 1), w_pad=2)
    fig.savefig(FIG / "fig5_invariance.pdf")
    plt.close(fig)


def main() -> None:
    resource_numbers()
    figure_gating()
    figure_lookup()
    figure_panels()
    invariance_numbers()
    lines = ["% Generated by preprint/scripts/make_figures.py - do not edit by hand."]
    for k, v in sorted(NUM.items()):
        lines.append(f"\\newcommand{{\\{k}}}{{{v}}}")
    (OUT / "numbers.tex").write_text("\n".join(lines) + "\n")
    print(f"wrote {len(NUM)} numbers, figures in {FIG}")


if __name__ == "__main__":
    main()
