/** The 12 CellTypist organ atlases (mirrors cella.core.config.ORGANS). */
export const ORGANS = [
  "Blood",
  "Bone marrow",
  "Heart",
  "Hippocampus",
  "Intestine",
  "Kidney",
  "Liver",
  "Lung",
  "Lymph node",
  "Pancreas",
  "Skeletal muscle",
  "Spleen",
] as const;

export const organSlug = (organ: string) => organ.replace(/ /g, "_");
