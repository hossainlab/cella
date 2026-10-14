"""Unit tests for prevalence-gated marker selection (no artifacts needed)."""

from __future__ import annotations

import pandas as pd

from cella.pipeline.emit import select_markers

GENES = ["CANON", "SILENT", "WEAK", "REPRESSOR", "ABSENT_EVERYWHERE"]


def _inputs() -> tuple[pd.Series, pd.Series, pd.Series]:
    coef = pd.Series([1.0, 5.0, 0.5, -2.0, -9.0], index=GENES)
    pct_in = pd.Series([0.9, 0.01, 0.4, 0.0, 0.0], index=GENES)
    pct_out_max = pd.Series([0.2, 0.0, 0.3, 0.8, 0.02], index=GENES)
    return coef, pct_in, pct_out_max


def test_positive_drops_genes_silent_in_the_cell_type() -> None:
    out = select_markers(*_inputs(), top_n=10, min_pct=0.1)
    # SILENT has the largest coefficient but is expressed in 1% of the cells.
    assert list(out["positive"].index) == ["CANON", "WEAK"]


def test_negative_requires_expression_elsewhere() -> None:
    out = select_markers(*_inputs(), top_n=10, min_pct=0.1)
    # ABSENT_EVERYWHERE is the most negative but no cell type expresses it.
    assert list(out["negative"].index)[0] == "REPRESSOR"
    assert "ABSENT_EVERYWHERE" not in out["negative"].index


def test_min_pct_zero_recovers_raw_ranking() -> None:
    coef, pct_in, pct_out_max = _inputs()
    out = select_markers(coef, pct_in, pct_out_max, top_n=2, min_pct=0.0)
    assert list(out["positive"].index) == ["SILENT", "CANON"]
    assert list(out["negative"].index) == ["ABSENT_EVERYWHERE", "REPRESSOR"]
