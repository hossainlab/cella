"""Benchmark the reverse lookup against external cell-type marker sets.

Reverse lookup takes a pasted gene list and ranks the atlas cell types it
defines. This module asks how often the top-ranked cell type is the right one,
using marker sets curated *outside* CellTypist as queries.

Queries
-------
Enrichr-hosted cell-type libraries (the canonical sources block scripted
downloads): ``Tabula_Sapiens``, ``Azimuth_2023``, ``CellMarker_2024`` and
``PanglaoDB_Augmented_2021``. Each term is reduced to a cell-type name (and a
tissue, where the library records one), the name is resolved to a Cell Ontology
id, and only human terms from tissues the atlas covers are kept.

Ground truth and matching
-------------------------
Methods rank *CL terms*: a CL term's score is the best score of any
(organ, curated label) annotated with it, so the organ is free and a query is
answered from whichever organ model fits best, as in the web tool.

* **exact** - the top term is the query's CL term.
* **relaxed** - the top term is the query's term, a descendant of it (a query
  for "T cell" answered with "CD4 T cell"), or a specific ancestor of it (one
  that is an ancestor of at most ``MAX_RELAXED_CHILDREN`` other atlas terms, so
  "leukocyte" never counts as a match).

A query is scored only if some atlas term could satisfy it under the relaxed
rule; queries for cell types the atlas does not contain are dropped and counted.
Queries whose term is too generic to be informative ("progenitor cell",
"epithelial cell": more than ``MAX_TRUTH_DESCENDANTS`` atlas descendants, any of
which would count as correct) are dropped as well.

The rank of the truth is ``1 + (#wrong terms scoring higher) + 0.5 * (#wrong
terms tied)``, which keeps tie-heavy methods (hypergeometric overlap) honest.

Leakage
-------
Some query sources share data with the CellTypist training atlases: Tabula
Sapiens trained the Bone marrow, Skeletal muscle and Spleen models, and the
Azimuth lung, heart and kidney references overlap Travaglini/Madissoon,
Litvinukova and Lake et al. Those queries are tagged ``overlap`` and the
headline numbers use ``independent`` queries only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

from cella.core.config import ORGANS

PROCESSED = Path("data/processed")
EXTERNAL = Path("data/external/enrichr")
ENRICHR_URL = "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName={}"
LIBRARIES = ("Tabula_Sapiens", "Azimuth_2023", "CellMarker_2024", "PanglaoDB_Augmented_2021")

MIN_PCT = 0.1  # same prevalence gate as the marker table
MAX_RELAXED_CHILDREN = 3
MAX_TRUTH_DESCENDANTS = 5
METHODS = (
    "weight_mean",
    "weight_gated",
    "weight_genez",
    "weight_genez_gated",
    "clf_pseudocell",
    "hybrid",
    "expr_pct",
    "expr_spec",
    "hypergeom",
)
# Pseudo-cell expression (log1p CP10k) assigned to every query gene: a gene
# that is clearly but not extremely expressed.
PSEUDOCELL_LEVEL = 2.0
# Score selection uses this library only; the others are held out for reporting.
DEV_LIBRARY = "CellMarker_2024"

# Library tissue string -> atlas organ. Tissues absent here are dropped.
TISSUE_TO_ORGAN: dict[str, dict[str, str]] = {
    "Tabula_Sapiens": {
        "Blood": "Blood",
        "Bone Marrow": "Bone marrow",
        "Heart": "Heart",
        "Kidney": "Kidney",
        "Large Intestine": "Intestine",
        "Small Intestine": "Intestine",
        "Liver": "Liver",
        "Lung": "Lung",
        "Lymph Node": "Lymph node",
        "Pancreas": "Pancreas",
        "Muscle": "Skeletal muscle",
        "Spleen": "Spleen",
    },
    "Azimuth_2023": {
        "PBMC": "Blood",
        "Bone Marrow": "Bone marrow",
        "Heart": "Heart",
        "Kidney": "Kidney",
        "Liver": "Liver",
        "Lung v1": "Lung",
        "Lung V2 (HLCA)": "Lung",
        "Pancreas": "Pancreas",
    },
    "CellMarker_2024": {
        "Blood": "Blood",
        "Peripheral Blood": "Blood",
        "Bone Marrow": "Bone marrow",
        "Marrow": "Bone marrow",
        "Heart": "Heart",
        "Hippocampus": "Hippocampus",
        "Intestine": "Intestine",
        "Small Intestine": "Intestine",
        "Colon": "Intestine",
        "Kidney": "Kidney",
        "Liver": "Liver",
        "Lung": "Lung",
        "Lymph Node": "Lymph node",
        "Lymph": "Lymph node",
        "Pancreas": "Pancreas",
        "Pancreatic Islet": "Pancreas",
        "Islet": "Pancreas",
        "Muscle": "Skeletal muscle",
        "Skeletal Muscle": "Skeletal muscle",
        "Spleen": "Spleen",
    },
}

# (library, organ) pairs whose source data overlaps the CellTypist training set.
OVERLAP: set[tuple[str, str]] = {
    ("Tabula_Sapiens", "Bone marrow"),
    ("Tabula_Sapiens", "Skeletal muscle"),
    ("Tabula_Sapiens", "Spleen"),
    ("Azimuth_2023", "Lung"),
    ("Azimuth_2023", "Heart"),
    ("Azimuth_2023", "Kidney"),
}


@dataclass(frozen=True)
class Query:
    """One external marker set with its resolved ground truth."""

    library: str
    term: str
    name: str
    organ: str | None  # tissue of origin mapped to an atlas organ, if recorded
    cl_id: str
    genes: tuple[str, ...]

    @property
    def stratum(self) -> str:
        return "overlap" if (self.library, self.organ) in OVERLAP else "independent"


# --------------------------------------------------------------------------- queries


def read_gmt(path: Path) -> dict[str, list[str]]:
    """Enrichr GMT: term, blank description, then genes (tab-separated)."""
    sets: dict[str, list[str]] = {}
    for line in path.read_text().splitlines():
        parts = [p for p in line.split("\t") if p]
        if len(parts) >= 2:
            sets[parts[0]] = [g.upper() for g in parts[1:]]
    return sets


def split_term(library: str, term: str) -> tuple[str, str | None] | None:
    """(cell-type name, library tissue) for a term, or None to drop it."""
    if library == "Tabula_Sapiens":
        tissue, _, name = term.partition("-")
        return name, tissue
    if library == "Azimuth_2023":
        for tissue in sorted(TISSUE_TO_ORGAN[library], key=len, reverse=True):
            if term.startswith(tissue + "-"):
                rest = term[len(tissue) + 1 :]
                return rest.partition("-")[2], tissue
        return None
    if library == "CellMarker_2024":
        if not term.endswith(" Human"):
            return None
        body = term[: -len(" Human")]
        for tissue in sorted(TISSUE_TO_ORGAN[library], key=len, reverse=True):
            if body.endswith(" " + tissue):
                return body[: -len(tissue) - 1], tissue
        return None
    return term, None  # PanglaoDB: no tissue


def _name_variants(name: str) -> list[str]:
    """Candidate CL labels for a free-text cell-type name, most literal first."""
    base = re.sub(r"\s+\d+$", "", name.strip())  # Azimuth cluster suffixes ("... 2")
    base = re.sub(r"\(.*?\)", "", base).strip()
    out = [base]
    low = base.lower()
    if low.endswith("cells"):
        out.append(base[:-1])
    if not low.endswith(("cell", "cells", "cyte", "cytes", "phage", "phages", "blast")):
        out.append(base + " cell")
    if low.endswith("s") and not low.endswith("cells"):
        out.append(base[:-1])
    return out


def resolve_cl(name: str) -> str | None:
    """Resolve a library cell-type name to a CL id via label, synonym, then variants."""
    from cella.pipeline.ontology import label_to_cl_id

    for candidate in _name_variants(name):
        cl_id = label_to_cl_id(candidate)
        if cl_id:
            return cl_id
    return None


def load_queries(external: Path = EXTERNAL) -> tuple[list[Query], pd.DataFrame]:
    """All resolvable atlas-tissue queries, plus a per-library accounting table."""
    queries: list[Query] = []
    accounting: list[dict[str, object]] = []
    for library in LIBRARIES:
        sets = read_gmt(external / f"{library}.gmt")
        counts = {"library": library, "terms": len(sets), "tissue_kept": 0, "resolved": 0}
        for term, genes in sets.items():
            split = split_term(library, term)
            if split is None:
                continue
            name, tissue = split
            organ = None
            if tissue is not None:
                organ = TISSUE_TO_ORGAN[library].get(tissue)
                if organ is None:
                    continue
            counts["tissue_kept"] += 1
            cl_id = resolve_cl(name)
            if cl_id is None:
                continue
            counts["resolved"] += 1
            queries.append(Query(library, term, name, organ, cl_id, tuple(genes)))
        accounting.append(counts)
    return queries, pd.DataFrame(accounting)


# --------------------------------------------------------------------------- ontology


@lru_cache(maxsize=4096)
def _ancestors(cl_id: str) -> frozenset[str]:
    from cella.pipeline.ontology import _parser

    try:
        return frozenset(_parser().get_term_ancestors(cl_id))
    except (KeyError, ValueError):
        return frozenset()


def correct_terms(truth: str, atlas_terms: list[str]) -> set[str]:
    """Atlas CL terms that count as a correct answer for ``truth`` (relaxed rule).

    Empty if no atlas term qualifies or ``truth`` is too generic to score.
    """
    if sum(truth in _ancestors(t) for t in atlas_terms) > MAX_TRUTH_DESCENDANTS:
        return set()
    n_children = {t: sum(t in _ancestors(o) for o in atlas_terms) for t in atlas_terms}
    ok = set()
    for term in atlas_terms:
        if term == truth or truth in _ancestors(term):
            ok.add(term)
        elif term in _ancestors(truth) and n_children[term] <= MAX_RELAXED_CHILDREN:
            ok.add(term)
    return ok


# --------------------------------------------------------------------------- scoring


@dataclass
class OrganIndex:
    """Per-organ matrices every method scores against, rows = curated labels."""

    organ: str
    cl_ids: np.ndarray  # (n_labels,)
    weights: pd.DataFrame
    weights_gated: pd.DataFrame
    pct: pd.DataFrame
    spec: pd.DataFrame  # per-gene z-score of mean expression across labels
    genez: pd.DataFrame  # per-gene z-score of coefficients across labels
    genez_gated: pd.DataFrame
    intercept: np.ndarray  # (n_labels,)
    z_zero: pd.Series  # scaled value of zero expression, per gene
    z_query: pd.Series  # scaled value of PSEUDOCELL_LEVEL, per gene
    markers: dict[str, frozenset[str]]  # curated label -> top-N positive markers


def build_index(processed: Path = PROCESSED) -> list[OrganIndex]:
    cto = pd.read_parquet(processed / "cell_type_organ.parquet")
    markers = pd.read_parquet(processed / "markers.parquet")
    markers = markers[markers["direction"] == "positive"]
    out: list[OrganIndex] = []
    for organ in ORGANS:
        slug = organ.replace(" ", "_")
        w = pd.read_parquet(processed / "weights" / f"{slug}.parquet")
        pct = pd.read_parquet(processed / "expression" / f"{slug}__pct.parquet").reindex(w.index)
        mean = pd.read_parquet(processed / "expression" / f"{slug}__mean.parquet").reindex(w.index)
        pct_in = pct.reindex(columns=w.columns).fillna(0.0)
        gated = w.where(~((w > 0) & (pct_in < MIN_PCT)), 0.0)
        sd = mean.std(axis=0).replace(0.0, np.nan)
        spec = ((mean - mean.mean(axis=0)) / sd).fillna(0.0)
        wsd = w.std(axis=0).replace(0.0, np.nan)
        genez = ((w - w.mean(axis=0)) / wsd).fillna(0.0)
        genez_gated = genez.where(~((genez > 0) & (pct_in < MIN_PCT)), 0.0)
        intercept, mu, scale = _model_offsets(organ, w)
        z_zero = ((0.0 - mu) / scale).clip(upper=10.0)
        z_query = ((PSEUDOCELL_LEVEL - mu) / scale).clip(upper=10.0)
        cl = cto[cto["organ"] == organ].set_index("curated_label")["cl_id"]
        mk = markers[markers["organ"] == organ].groupby("cell_type")["gene"].apply(list)
        out.append(
            OrganIndex(
                organ=organ,
                cl_ids=cl.reindex(w.index).to_numpy(dtype=object),
                weights=w,
                weights_gated=gated,
                pct=pct,
                spec=spec,
                genez=genez,
                genez_gated=genez_gated,
                intercept=intercept,
                z_zero=z_zero,
                z_query=z_query,
                markers={str(k): frozenset(v) for k, v in mk.items()},
            )
        )
    return out


def _model_offsets(organ: str, w: pd.DataFrame) -> tuple[np.ndarray, pd.Series, pd.Series]:
    """Intercepts and the scaler's per-gene mean/scale, aligned to the weight matrix."""
    import pickle

    from cella.analysis.invariance import model_file

    with model_file(organ).open("rb") as handle:
        payload = pickle.load(handle)  # noqa: S301 - first-party CellTypist release
    clf, scaler = payload["Model"], payload["Scaler_"]
    genes = pd.Index(np.asarray(clf.features).astype(str))
    labels = [str(c) for c in clf.classes_]
    intercept = pd.Series(clf.intercept_, index=labels).reindex(w.index.astype(str)).to_numpy()
    mu = pd.Series(scaler.mean_, index=genes).reindex(w.columns)
    scale = pd.Series(scaler.scale_, index=genes).reindex(w.columns)
    return intercept, mu, scale


def _pseudocell(idx: OrganIndex, genes: list[str]) -> np.ndarray | None:
    """Softmax probability per label for a cell expressing exactly the query genes."""
    present = [g for g in genes if g in idx.weights.columns]
    if not present:
        return None
    w = idx.weights.to_numpy()
    base = idx.intercept + w @ idx.z_zero.to_numpy()
    delta = (idx.z_query[present] - idx.z_zero[present]).to_numpy()
    logits = base + idx.weights[present].to_numpy() @ delta
    logits = logits - logits.max()
    prob = np.exp(logits)
    return prob / prob.sum()


def _zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else np.zeros_like(x)


def _mean_over(matrix: pd.DataFrame, genes: list[str]) -> np.ndarray | None:
    present = [g for g in genes if g in matrix.columns]
    if not present:
        return None
    return matrix[present].to_numpy().mean(axis=1)


def score_organ(idx: OrganIndex, genes: list[str], method: str) -> np.ndarray | None:
    """Per-label scores for one organ, or None if no query gene is in its vocabulary."""
    if method == "weight_mean":
        return _mean_over(idx.weights, genes)
    if method == "weight_gated":
        return _mean_over(idx.weights_gated, genes)
    if method == "weight_genez":
        return _mean_over(idx.genez, genes)
    if method == "weight_genez_gated":
        return _mean_over(idx.genez_gated, genes)
    if method == "clf_pseudocell":
        return _pseudocell(idx, genes)
    if method == "hybrid":
        a = _mean_over(idx.genez_gated, genes)
        b = _mean_over(idx.pct, genes)
        if a is None or b is None:
            return None
        return (_zscore(a) + _zscore(b)) / 2.0
    if method == "expr_pct":
        return _mean_over(idx.pct, genes)
    if method == "expr_spec":
        return _mean_over(idx.spec, genes)
    if method == "hypergeom":
        universe = set(idx.weights.columns)
        q = universe.intersection(genes)
        if not q:
            return None
        n_total = len(universe)
        scores = []
        for label in idx.weights.index:
            m = idx.markers.get(str(label), frozenset())
            k = len(q & m)
            p = hypergeom.sf(k - 1, n_total, len(m), len(q)) if k else 1.0
            scores.append(-np.log10(max(p, 1e-300)))
        return np.asarray(scores)
    raise ValueError(f"unknown method: {method}")


def score_terms(index: list[OrganIndex], genes: list[str], method: str) -> pd.Series:
    """Best score per atlas CL term across every organ model."""
    best: dict[str, float] = {}
    for idx in index:
        scores = score_organ(idx, genes, method)
        if scores is None:
            continue
        for cl_id, s in zip(idx.cl_ids, scores, strict=True):
            if isinstance(cl_id, str) and s > best.get(cl_id, -np.inf):
                best[cl_id] = float(s)
    return pd.Series(best, dtype=float)


def truth_rank(scores: pd.Series, correct: set[str]) -> float:
    """Rank of the best-scoring correct term among the wrong ones (ties count half)."""
    hit = scores[scores.index.isin(list(correct))]
    if hit.empty:
        return float("nan")
    top = hit.max()
    wrong = scores[~scores.index.isin(list(correct))]
    return 1.0 + float((wrong > top).sum()) + 0.5 * float((wrong == top).sum())


def evaluate(
    queries: list[Query],
    index: list[OrganIndex],
    methods: tuple[str, ...] = METHODS,
    subsample: int | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """One row per (query, method) with exact and relaxed ranks.

    With ``subsample``, each query is cut to that many genes drawn from those in
    any model vocabulary (queries with fewer are skipped), mimicking a user who
    pastes a handful of markers.
    """
    atlas_terms = sorted({c for idx in index for c in idx.cl_ids if isinstance(c, str)})
    vocab = set().union(*(idx.weights.columns for idx in index))
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for q in queries:
        relaxed = correct_terms(q.cl_id, atlas_terms)
        if not relaxed:
            continue
        genes = [g for g in q.genes if g in vocab]
        if subsample is not None:
            if len(genes) < subsample:
                continue
            genes = list(rng.choice(genes, size=subsample, replace=False))
        if not genes:
            continue
        for method in methods:
            scores = score_terms(index, genes, method)
            rows.append(
                {
                    "library": q.library,
                    "term": q.term,
                    "organ": q.organ,
                    "cl_id": q.cl_id,
                    "stratum": q.stratum,
                    "n_genes": len(genes),
                    "method": method,
                    "rank_exact": truth_rank(scores, {q.cl_id}),
                    "rank_relaxed": truth_rank(scores, relaxed),
                    "top_term": scores.idxmax() if not scores.empty else None,
                }
            )
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame, by: tuple[str, ...] = ("method",)) -> pd.DataFrame:
    """Top-1/3/5 accuracy and MRR per group; exact-rank metrics skip NaN (truth absent)."""

    def agg(g: pd.DataFrame) -> pd.Series:
        rel, ex = g["rank_relaxed"], g["rank_exact"].dropna()
        return pd.Series(
            {
                "n": len(g),
                "top1": (rel <= 1).mean(),
                "top3": (rel <= 3).mean(),
                "top5": (rel <= 5).mean(),
                "mrr": (1.0 / rel).mean(),
                "n_exact": len(ex),
                "top1_exact": (ex <= 1).mean() if len(ex) else np.nan,
                "top5_exact": (ex <= 5).mean() if len(ex) else np.nan,
            }
        )

    return results.groupby(list(by)).apply(agg, include_groups=False).reset_index()


def confidence_calibration(
    queries: list[Query],
    index: list[OrganIndex],
    method: str = "expr_pct",
    min_scores: tuple[float, ...] = (0.3,),
    min_margins: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.25),
) -> pd.DataFrame:
    """Precision of the reverse-lookup confidence call per threshold, dev vs test.

    Mirrors the API rule: confident when the top term's score reaches
    ``min_score`` and it leads the best term that is neither itself nor a close
    ontology relative (``cella.pipeline.ontology.close_relatives``) by
    ``min_margin`` of its score. Uses independent queries only.
    """
    from cella.pipeline.ontology import close_relatives

    atlas_terms = sorted({c for idx in index for c in idx.cl_ids if isinstance(c, str)})
    allied = {t: rel | {t} for t, rel in close_relatives(atlas_terms).items()}
    rows = []
    for q in queries:
        if q.stratum != "independent":
            continue
        correct = correct_terms(q.cl_id, atlas_terms)
        if not correct:
            continue
        scores = score_terms(index, list(q.genes), method).sort_values(ascending=False)
        if scores.empty:
            continue
        top_term, top = scores.index[0], float(scores.iloc[0])
        others = scores[~scores.index.isin(list(allied.get(top_term, {top_term})))]
        runner_up = float(others.iloc[0]) if len(others) else 0.0
        rows.append(
            {
                "split": "dev" if q.library == DEV_LIBRARY else "test",
                "top": top,
                "margin": (top - runner_up) / top if top > 0 else 0.0,
                "correct": top_term in correct,
            }
        )
    d = pd.DataFrame(rows)
    out = []
    for min_score in min_scores:
        for min_margin in min_margins:
            for split, x in d.groupby("split"):
                conf = (x["top"] >= min_score) & (x["margin"] >= min_margin)
                out.append(
                    {
                        "min_score": min_score,
                        "min_margin": min_margin,
                        "split": split,
                        "n": len(x),
                        "confident_frac": conf.mean(),
                        "precision_confident": x.loc[conf, "correct"].mean(),
                        "precision_rest": x.loc[~conf, "correct"].mean(),
                    }
                )
    return pd.DataFrame(out)
