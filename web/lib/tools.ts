// Single source of truth for the platform's tools. The nav and the homepage
// both render from this list, so adding a module here wires it into both.

export type ToolStatus = "live" | "planned";

export interface Tool {
  slug: string;
  name: string;
  href: string;
  status: ToolStatus;
  question: string; // the question the tool answers, in plain language
  blurb: string;
}

export const TOOLS: Tool[] = [
  {
    slug: "organ-browser",
    name: "Organ Browser",
    href: "/organs",
    status: "live",
    question: "What's in each organ atlas?",
    blurb:
      "Browse the 12 organs — datasets, donors, cell-type composition, and expression.",
  },
  {
    slug: "marker-atlas",
    name: "Marker Atlas",
    href: "/marker-atlas",
    status: "live",
    question: "What genes define a cell type?",
    blurb:
      "Universal core identity vs. tissue-adapted markers for any cell type, across 12 organs.",
  },
  {
    slug: "reverse-lookup",
    name: "Reverse Lookup",
    href: "/reverse-lookup",
    status: "live",
    question: "My markers — which cell type is this?",
    blurb:
      "Paste a gene signature; Cella ranks the cell types that express it across 12 organs, and flags ambiguous or novel states.",
  },
  {
    slug: "fingerprint",
    name: "Fingerprint Explorer",
    href: "/fingerprint",
    status: "live",
    question: "How does the same cell type differ across organs?",
    blurb:
      "Side-by-side discriminative-weight fingerprints — the top +/- genes per organ.",
  },
  {
    slug: "graph",
    name: "Relationship Graph",
    href: "/graph",
    status: "live",
    question: "How do all the cell types relate?",
    blurb:
      "An interactive cross-organ graph of the harmonized cell types and how they cluster.",
  },
];
