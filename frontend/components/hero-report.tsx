import { api, type GapReport } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";

/**
 * The hero visual is a real gap report, not a mockup.
 *
 * References for this kind of page usually place an illustration of the
 * product beside the headline. Here the product's own output is more
 * convincing than a drawing of it, and it costs nothing extra: the data is
 * already an API call away.
 *
 * If the API is cold the component renders nothing rather than a broken
 * frame, so the landing page still reads.
 */

// Chosen for a readable spread of categories in its top gaps. Since gaps are
// ranked within a course's own subject area, a single course no longer
// produces five different colours, so this one is picked rather than taken
// arbitrarily.
const HERO_COURSE = "BCA1521 ARTIFICIAL INTELLIGENCE";

export async function HeroReport() {
  let report: GapReport | null = null;

  try {
    report = await api.gaps(HERO_COURSE);
  } catch {
    return null;
  }

  // An unscored course is one the corpus could not judge. It has nothing to
  // show here, and the hero degrades to the copy alone rather than a card
  // reporting "n/a".
  if (!report || report.gaps.length === 0 || report.health_score == null) {
    return null;
  }

  const gaps = report.gaps.slice(0, 5);

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)]">
      {/* The header carries the block colour so the card reads as part of the
          palette rather than as a white panel dropped onto the canvas. */}
      <div
        className="flex items-baseline justify-between gap-4 px-6 py-5"
        style={{ backgroundColor: "var(--color-block-periwinkle)" }}
      >
        <div className="min-w-0">
          <p className="micro-cap text-[var(--color-ink)]/70">
            Live gap report
          </p>
          <p className="card-title mt-1.5 truncate text-[var(--color-ink)]">
            {report.course_title.replace(/^BCA\d+\s*/, "")}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="tabular text-[42px] font-light leading-none text-[var(--color-ink)]">
            {report.health_score.toFixed(1)}
          </p>
          <p className="micro-cap mt-1 text-[var(--color-ink)]/70">alignment</p>
        </div>
      </div>

      <div className="divide-y divide-[var(--color-hairline)]">
        {gaps.map((gap) => {
          const block = categoryBlock(gap.category);
          const share = Math.round(gap.market_demand * 100);

          return (
            <div key={gap.canonical_skill} className="px-6 py-3.5">
              <div className="flex items-baseline gap-3">
                <span className="min-w-0 flex-1 truncate text-[15px] font-medium text-[var(--color-ink)]">
                  {gap.canonical_skill}
                </span>
                <span className="tabular shrink-0 text-[15px] text-[var(--color-ink-mute)]">
                  {gap.postings_requiring} of {gap.postings_total}
                </span>
              </div>

              {/* Demand as a bar the eye can compare across rows, in the
                  category's own colour. A dot showed the category but not the
                  magnitude, and the previous bar was too thin to read. */}
              <div className="mt-2 flex items-center gap-3">
                <span className="block h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--color-canvas)]">
                  <span
                    className="block h-full rounded-full"
                    style={{
                      width: `${Math.max(8, share)}%`,
                      backgroundColor: block.dot,
                    }}
                  />
                </span>
                <span className="micro-cap shrink-0 text-[var(--color-ink-mute)]">
                  {block.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="caption border-t border-[var(--color-hairline)] px-6 py-4 text-[var(--color-ink-mute)]">
        {report.gaps.length} gaps found, ranked by demand weighted against what
        the syllabus already covers.
      </p>
    </div>
  );
}
