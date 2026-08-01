/**
 * Skill categories mapped to the pastel block palette in DESIGN.md.
 *
 * The mapping is fixed rather than generated, so a category means the same
 * colour on the dashboard, in a gap card, and on a graph node. Colour that
 * shifts between views is decoration; colour that holds is information.
 */

export const CATEGORY_BLOCKS: Record<string, { bg: string; dot: string; label: string }> = {
  ai: { bg: "var(--color-block-lilac)", dot: "#7c5cd6", label: "AI and ML" },
  data: { bg: "var(--color-block-sky)", dot: "#3d7ab8", label: "Data" },
  web: { bg: "var(--color-block-lime)", dot: "#6f9435", label: "Web" },
  cloud: { bg: "var(--color-block-mint)", dot: "#3f8c5c", label: "Cloud" },
  systems: { bg: "var(--color-block-coral)", dot: "#c26a3d", label: "Systems" },
  security: { bg: "var(--color-block-pink)", dot: "#b8536a", label: "Security" },
  engineering: { bg: "var(--color-block-cream)", dot: "#9c7c3a", label: "Engineering" },
  language: { bg: "var(--color-block-lime)", dot: "#6f9435", label: "Languages" },
  foundations: { bg: "var(--color-surface-soft)", dot: "#767676", label: "Foundations" },
  mathematics: { bg: "var(--color-surface-soft)", dot: "#767676", label: "Mathematics" },
  professional: { bg: "var(--color-surface-soft)", dot: "#8a8a8a", label: "Professional" },
};

const FALLBACK = {
  bg: "var(--color-surface-soft)",
  dot: "#767676",
  label: "General",
};

export function categoryBlock(category: string | undefined) {
  return (category && CATEGORY_BLOCKS[category]) || FALLBACK;
}

/** Rotating block colours for sections that are not category-specific. */
export const SECTION_BLOCKS = [
  "var(--color-block-lime)",
  "var(--color-block-lilac)",
  "var(--color-block-cream)",
  "var(--color-block-mint)",
  "var(--color-block-pink)",
] as const;
