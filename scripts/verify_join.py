"""Verify that obs["Curated_annotation"] is the exact join key for the model labels,
across every cached organ. Exits non-zero if any organ fails to match exactly.

Usage: uv run --group pipeline python scripts/verify_join.py
"""

from __future__ import annotations

import sys

import celltypist
import pandas as pd

from cella.core.config import ORGANS
from cella.pipeline.acquire import model_path, obs_path

JOIN_COL = "Curated_annotation"


def main() -> int:
    rows = []
    ok = True
    for organ in ORGANS:
        if not obs_path(organ).exists():
            rows.append((organ, "-", "-", "obs not cached"))
            ok = False
            continue
        model = celltypist.models.Model.load(str(model_path(organ)))
        obs = pd.read_parquet(obs_path(organ))
        model_labels = set(model.cell_types)
        curated = (
            set(obs[JOIN_COL].dropna().astype(str)) if JOIN_COL in obs.columns else set()
        )
        exact = model_labels == curated
        ok = ok and exact
        note = "exact" if exact else f"MISSING={sorted(model_labels - curated)}"
        rows.append((organ, len(model_labels), len(curated), note))

    width = max(len(r[0]) for r in rows)
    for organ, m, c, note in rows:
        print(f"{organ:<{width}}  model={m!s:>3}  curated={c!s:>3}  {note}")
    print("\nRESULT:", "ALL EXACT ✓" if ok else "MISMATCH ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
