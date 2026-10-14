# Cella preprint

`main.tex` is the manuscript; `main.pdf` is the compiled output.

Every number in the text is a macro from `numbers.tex`, and the tables and
figures are generated too, so the manuscript cannot drift from the data.
Regenerate them after any change to the artifacts or benchmarks:

```bash
# from the repository root
uv run --group api cella export --out web/public/data          # export sizes
uv run --group analysis python scripts/lookup_benchmark.py      # if the lookup changed
uv run --group analysis python preprint/scripts/make_figures.py # figures + numbers.tex
cd preprint && tectonic -X compile main.tex
```

| File | Source |
|---|---|
| `numbers.tex`, `table_*.tex`, `supplementary_*.csv`, `figures/fig{2..5}_*.pdf` | `scripts/make_figures.py` |
| `numbers_manual.tex` | static-vs-server check, `web/scripts/check-static.ts` (update by hand) |
| `figures/fig1_*.png` | screenshots of the public site, light theme |
| `references.bib` | PubMed records via NCBI E-utilities (DOIs and PMIDs verified) |

Before posting: add the Zenodo DOI to the data-availability statement
(`main.tex`, marked `TODO`).
