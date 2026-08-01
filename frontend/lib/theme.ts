/**
 * Skill categories mapped to the pastel block palette in DESIGN.md.
 *
 * The mapping is fixed rather than generated, so a category means the same
 * colour on the dashboard, in a gap card, and on a graph node. Colour that
 * shifts between views is decoration; colour that holds is information.
 */

export const CATEGORY_BLOCKS: Record<string, { bg: string; dot: string; label: string }> = {
  ai: { bg: "var(--color-block-periwinkle)", dot: "#5b4bab", label: "AI and ML" },
  data: { bg: "var(--color-block-sky)", dot: "#2f6690", label: "Data" },
  web: { bg: "var(--color-block-moss)", dot: "#5c7027", label: "Web" },
  cloud: { bg: "var(--color-block-sage)", dot: "#2f7d5b", label: "Cloud" },
  systems: { bg: "var(--color-block-clay)", dot: "#9c542a", label: "Systems" },
  security: { bg: "var(--color-block-orchid)", dot: "#a02f96", label: "Security" },
  engineering: { bg: "var(--color-block-butter)", dot: "#8a6d14", label: "Engineering" },
  language: { bg: "var(--color-block-moss)", dot: "#5c7027", label: "Languages" },
  foundations: { bg: "var(--color-block-stone)", dot: "#6d6c62", label: "Foundations" },
  mathematics: { bg: "var(--color-block-stone)", dot: "#6d6c62", label: "Mathematics" },
  professional: { bg: "var(--color-block-stone)", dot: "#7b7f86", label: "Professional" },
};

const FALLBACK = {
  bg: "var(--color-block-stone)",
  dot: "#7b7f86",
  label: "General",
};

export function categoryBlock(category: string | undefined) {
  return (category && CATEGORY_BLOCKS[category]) || FALLBACK;
}

/** Rotating block colours for sections that are not category-specific. */
export const SECTION_BLOCKS = [
  "var(--color-block-moss)",
  "var(--color-block-periwinkle)",
  "var(--color-block-butter)",
  "var(--color-block-sage)",
  "var(--color-block-orchid)",
] as const;
