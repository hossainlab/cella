## Role
You are a Senior Computational Biologist, Bioinformatics Software Architect, Full-Stack Engineer, and UI/UX Designer with expertise in single-cell transcriptomics, Python, Next.js, PostgreSQL, FastAPI, Scanpy, CellTypist, CellHint and scientific software engineering. Your task is to help me develop a production-quality, open-source research platform for single-cell transcriptomics.

## Project Vision
- The platform is NOT another single-cell database and NOT another UMAP viewer.
- Instead, it is a knowledge and decision-support platform built on top of the CellTypist Organ Atlases (https://www.celltypist.org/organs) and pretrained annotation models.
- The platform should transform CellTypist reference resources into a searchable biological knowledge engine that helps researchers interpret and compare single-cell data.

## Data Sources
The platform must use only the official CellTypist resources:
- Organ Atlas (.h5ad)
- Pretrained annotation models (.pkl)
- Official CellTypist metadata

No additional atlases or reference datasets should be included in Version 1.

## What the CellTypist Organ Atlas Uniquely Offers
The CellTypist organ atlas (celltypist.org/organs) is not just a collection of cell-type labels. It is a deeply curated cross-tissue resource with several underexploited assets [1, 2]:

12 human organ atlases (Blood, Bone marrow, Heart, Hippocampus, Intestine, Kidney, Liver, Lung, Lymph node, Pancreas, Skeletal muscle, Spleen), integrating 38 datasets into >3.6 million cells and ~250 cell types [2]

Logistic-regression classifiers for each organ, where every gene has a learned weight per cell type — these weights are directly interpretable as discriminative markers, accessible via model.extract_top_markers() and model.classifier.coef_ [3, 4]
Hierarchical resolution — each cell type exists at "Low" (high-resolution subtypes) and "High" (low-resolution broad classes) levels [5]

A cross-tissue relationship graph built by CellTypist v2.0's predictive clustering tree approach, which hierarchically defines shared and novel cell subtypes across tissues [2]

Cell Ontology IDs mapped to most cell types, enabling linkage to the broader Cell Ontology [6]
The key insight for novelty: almost no existing web tool exposes the classifier weights or the cross-organ relationship graph interactively. Most atlas browsers show expression; almost none show what discriminates a cell type.

## Novel Web Tool Concepts
1. Cross-Organ Cell-Type Fingerprint Explorer
What it does: An interactive web tool where you select a cell type (e.g., "macrophage," "fibroblast," "endothelial cell") and see how its discriminative gene fingerprint differs across all organs where it appears. For each organ, the tool shows the top positive and negative classifier weights — the genes that most distinguish that cell type from others in that tissue. A heatmap or radar plot compares fingerprints side-by-side; clicking a gene shows its weight across all organs.

Why it's novel: The cross-tissue fibroblast and macrophage papers [13, 24, 25] did this analytically in publications, but no interactive tool exposes it. Cytomarker [20] designs panels from expression, not from discriminative weights. The classifier-weight angle answers a different question than expression: not "is this gene expressed" but "is this gene what defines this cell type here."

Who it serves: Researchers comparing cell-type biology across tissues; industry teams assessing whether a target's discriminative cell type is the same across organs (on-target safety); learners understanding what makes a cell type what it is.

Atlas data leveraged: All 12 organ models' classifier.coef_ matrices + cell-type hierarchy.

Feasibility: High. Weights are pre-computed in the .pkl models; the tool is a visualization layer on top of extracted coefficient matrices. No heavy compute at runtime.

2. The Cell-Type Relationship Graph Explorer
What it does: An interactive, navigable graph of the ~250 cell types across 12 organs, built from CellTypist v2.0's cross-tissue relationship graph [2]. Nodes are cell types (sized by cell count, colored by organ or lineage); edges represent transcriptomic similarity / shared subtypes. Users can zoom from "High" (broad classes) to "Low" (fine subtypes) resolution, filter by organ, search for a cell type and see where it clusters, and click an edge to see what two cell types share. A slider collapses/expands the hierarchy.

Why it's novel: CellTypist v2.0 built this relationship graph [2] but it exists only in the paper and as code output — there is no interactive web explorer for it. tissueimmunecellatlas.org [12] shows a dendrogram but only for immune cells. A cross-organ, hierarchical, interactive graph of all 250 cell types does not exist as a web tool.

Who it serves: Researchers navigating cell-type nomenclature across tissues; learners who want to see how cell types relate; industry teams identifying shared vs. tissue-specific populations.

Atlas data leveraged: The cross-tissue relationship graph from CellTypist v2.0, the hierarchical Low/High structure, Cell Ontology mappings.

Feasibility: Medium. The graph structure needs to be extracted/recomputed from the atlas data (the v2.0 tree approach), then rendered with a graph library (D3, Cytoscape.js, or vis.js). One-time compute, then static serving.

3. Discriminative Marker Atlas ("What Defines a Cell Type")
What it does: A web tool that flips the usual question. Instead of "which cell types express gene X" (CELLxGENE already does this [7]), it answers "which genes define cell type Y" — using the classifier weights across all 12 organs. For any cell type, you see: (a) its top discriminative genes per organ, (b) a "consensus" set of genes that are discriminative in every organ where the cell type appears (the universal core identity), and (c) organ-specific discriminative genes (the tissue-adapted identity). Each gene links to its weight, direction, and the organ context.

Why it's novel: Cell Guide [7] provides curated markers per cell type, but these are literature-curated, not data-driven discriminative weights. No tool distinguishes "universal identity genes" from "tissue-adapted identity genes" using a consistent ML framework across 12 organs. This is a fundamentally different and more rigorous view of cell-type identity.

Who it serves: Researchers designing markers / probes / panels; learners building intuition about cell-type identity; industry teams selecting biomarkers that are robust across tissues vs. tissue-specific.

Atlas data leveraged: All 12 organ models' coefficient matrices, cross-referenced by cell-type name and Cell Ontology ID.

Feasibility: High. Pure visualization on pre-extracted weights. The "consensus vs. tissue-specific" split is a set operation across organs.

4. Cell-Type Identity Quiz / Learning Tool
What it does: An educational web app built on the atlas. It shows a learner a cell type's discriminative genes (from classifier weights), its organ context, and its position in the hierarchy, then asks them to identify it — or shows two cell types and asks which genes distinguish them. Progressive difficulty: start at "High" resolution (broad classes), advance to "Low" (fine subtypes). Includes a "build your own cell type" mode where learners select genes and see which cell type across which organs best matches.

Why it's novel: Existing educational resources are static (textbooks, Cell Guide encyclopedia [7]). No interactive, data-driven learning tool uses real discriminative weights to teach cell-type identity across organs. The "build your own cell type" mode (select genes → see which cell type matches) is genuinely novel and pedagogically powerful.

Who it serves: Learners and students primarily; also researchers new to a tissue who want to quickly learn its cell-type landscape.

Atlas data leveraged: Classifier weights + cell-type hierarchy + organ metadata.

Feasibility: High. The "build your own cell type" mode is a lightweight nearest-cell-type lookup using the weight vectors.

5. Tissue-Specificity Score Explorer
What it does: For every cell type in the atlas, compute a "tissue-specificity score" — how restricted is this cell type to one organ vs. shared across many? Display as an interactive sortable table / heatmap: cell types ranked by specificity, with their organ distribution, discriminative genes, and Cell Ontology ID. Users can filter to "tissue-specific only" or "shared across all organs" and export lists. A companion view shows, for each organ, which cell types are unique to it vs. borrowed from common populations.

Why it's novel: The concept of tissue-specificity exists in expression atlases (GTEx tau scores), but applying it to cell-type distribution across organs using a harmonized 12-organ atlas is not available as an interactive tool. This directly serves the "what's unique to this organ" question that researchers and translational teams ask.

Who it serves: Industry / translational (tissue-specific target discovery, on-target safety); researchers studying organ biology; learners understanding organ cellular composition.

Atlas data leveraged: Cell-type counts per organ, the harmonized cell-type labels, Cell Ontology IDs.

Feasibility: High. Cell counts per organ per cell type are derivable from the atlas metadata; the score is a simple entropy or Gini calculation.

6. "Is My Cell Type Novel?" — Query Against the 12-Organ Atlas
What it does: A web tool where a researcher who has a new cluster (defined by a few marker genes or a small expression profile) can check whether it matches a known cell type in any of the 12 organ atlases. Input: a gene list or a small expression vector. Output: the closest matching cell types across organs, with discriminative genes, confidence, and a note on whether the match is strong, partial, or potentially novel (no good match). This is a lightweight, no-upload version — users just paste markers.

Why it's novel: Annotation services (CellTypist, popV [15]) require uploading full data. Cell Guide [7] is a lookup but doesn't score matches. A lightweight "paste your markers, see if this cell type exists in our 12-organ reference" tool with a novelty flag is a different, lower-friction entry point — especially for researchers with a cluster and a few markers who just want to know "is this new?"

Who it serves: Researchers annotating their own data who want a quick check before full annotation; learners; industry teams evaluating novelty of a population.

Atlas data leveraged: Classifier weights as a lookup index; cell-type hierarchy for reporting matches at multiple resolutions.

Feasibility: High. Marker-to-cell-type matching via cosine similarity against weight vectors; no data upload or heavy compute.

Tier 3 — Interesting but more crowded or more complex
7. Cross-Organ Cell-Type Composition Comparator
What it does: Interactive comparison of cell-type composition across organs — stacked bar charts, heatmaps, and statistical tests for compositional differences. Select organs to compare, select cell-type resolution, see which cell types expand or contract.

Why it's less novel: Compositional analysis tools exist (scCODA, etc.), and CELLxGENE [7] enables some cross-dataset comparison. The novelty is in the harmonized 12-organ framing, but the visualization concept is well-trodden.

Feasibility: High.

8. Target-to-Cell-Type Mapper (Translational)
What it does: Input a gene (drug target), see which cell types across which organs have it as a discriminative marker (not just expressed). This distinguishes "your target is a defining feature of macrophages in lung but not liver" from "your target is broadly expressed." Adds a safety layer: if a target is discriminative for a cell type in a vital organ, flag it.

Why it's partially novel: The discriminative-weight angle is novel vs. expression-only tools, but the overall concept (target → cell type → tissue → safety) overlaps with existing target-safety tools and skills. More crowded space.

Feasibility: Medium (needs careful framing to avoid overclaiming safety from classifier weights).

Summary: Recommended Focus for Maximum Novelty
The three Tier-1 concepts share a common, underexploited asset: the CellTypist classifier weights and the cross-organ relationship graph. They answer questions no existing web tool answers:

Fingerprint Explorer — "How does the same cell type differ across organs?" (discriminative-gene level)
Relationship Graph Explorer — "How do all 250 cell types across 12 organs relate to each other?" (interactive, hierarchical)
Discriminative Marker Atlas — "What genes define each cell type, and which are universal vs. tissue-adapted?"
All three are feasible as static-data web apps (pre-compute weights/graph once, serve interactively), serve all three audiences (researchers, learners, industry), and leverage what is genuinely unique about the CellTypist organ atlas.

References
[1] CellTypist organs page, https://www.celltypist.org/organs [2] Xu et al., "Automatic cell-type harmonization and integration across Human Cell Atlas datasets," Cell 186, 5876–5891.e20 (2023) [3] CellTypist GitHub, https://github.com/Teichlab/celltypist [4] CellTypist Model API, https://celltypist.readthedocs.io/en/latest/celltypist.models.Model.html [5] CellTypist models page, https://www.celltypist.org/models [6] "The Cell Ontology in the age of single-cell omics," Scientific Data (2026) [7] CZ CELLxGENE Discover, https://cellxgene.cziscience.com/ [8] UCSC Cell Browser, https://cells.ucsc.edu/ [9] Single Cell Portal, https://singlecell.broadinstitute.org/ [10] BBrowser (BioTuring), https://bioturing.com/bbrowser [11] SCE, https://ctlab.github.io/SCE/ [12] Cross-tissue Immune Cell Atlas, https://www.tissueimmunecellatlas.org/ [13] Fibroblast Atlas, https://www.science.org/doi/10.1126/sciadv.ado0173 [14] Organ fibrosis explorer, https://organfibrosis.saezlab.org/ [15] popV, Nature Genetics (2024), https://www.nature.com/articles/s41588-024-01993-3 [16] AnnQ, Briefings in Bioinformatics (2025) [17] Conformalized single-cell annotator, https://github.com/digital-medicine-research-group-UNAV/conformalized_single_cell_annotator [18] scCertify, PMC10957513 [19] MOSAIC, bioRxiv (2026) [20] Cytomarker, bioRxiv (2024), https://www.biorxiv.org/content/10.1101/2024.10.15.618479v1 [21] EasyPanel, https://www.easypanel.ai/ [22] ImapDB, bioRxiv (2025) [23] Lamin + CellTypist, https://docs.lamin.ai/celltypist [24] Cross-tissue fibroblast atlas, Cell (2024) [25] Human fibroblast-myeloid atlas, bioRxiv (2025)
