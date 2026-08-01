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

const HERO_COURSE = "BCA1513 WEB APPLICATION DEVELOPMENT";

export async function HeroReport() {
  let report: GapReport | null = null;

  try {
    report = await api.gaps(HERO_COURSE);
  } catch {
    return null;
  }

  if (!report || report.gaps.length === 0) return null;

  const gaps = report.gaps.slice(0, 5);

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)]">
      <div className="flex items-baseline justify-between gap-4 border-b border-[var(--color-hairline)] px-6 py-5">
        <div className="min-w-0">
          <p className="micro-cap text-[var(--color-ink-mute)]">
            Live gap report
          </p>
          <p className="card-title mt-1.5 truncate text-[var(--color-ink)]">
            {report.course_title.replace(/^BCA\d+\s*/, "")}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="tabular text-[36px] font-light leading-none text-[var(--color-ink)]">
            {report.health_score.toFixed(1)}
          </p>
          <p className="micro-cap mt-1 text-[var(--color-ink-mute)]">
            alignment
          </p>
        </div>
      </div>

      <div className="divide-y divide-[var(--color-hairline)]">
        {gaps.map((gap) => {
          const block = categoryBlock(gap.category);
          const share = Math.round(gap.market_demand * 100);

          return (
            <div
              key={gap.canonical_skill}
              className="flex items-center gap-4 px-6 py-3.5"
            >
              <span
                aria-hidden
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: block.dot }}
              />
              <span className="min-w-0 flex-1 truncate text-[15px] text-[var(--color-ink)]">
                {gap.canonical_skill}
              </span>
              <span className="tabular shrink-0 text-[15px] text-[var(--color-ink-mute)]">
                {gap.postings_requiring} of {gap.postings_total}
              </span>
              <span className="w-16 shrink-0">
                <span className="block h-1 w-full overflow-hidden rounded-full bg-[var(--color-hairline)]">
                  <span
                    className="block h-full rounded-full"
                    style={{
                      width: `${Math.max(6, share)}%`,
                      backgroundColor: block.dot,
                    }}
                  />
                </span>
              </span>
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
