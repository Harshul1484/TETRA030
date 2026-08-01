import Link from "next/link";

import { api, type CourseSummary, type MarketSummary } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorPanel,
  HealthScore,
  SectionTitle,
  Stat,
} from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let courses: CourseSummary[] = [];
  let market: MarketSummary | null = null;
  let error: string | null = null;

  try {
    [courses, market] = await Promise.all([api.courses(), api.marketSummary()]);
  } catch (exception) {
    error = exception instanceof Error ? exception.message : String(exception);
  }

  if (error) return <ErrorPanel message={error} />;

  const scored = courses.filter((course) => course.health_score !== null);
  const programAlignment =
    scored.length > 0
      ? scored.reduce((sum, course) => sum + (course.health_score ?? 0), 0) /
        scored.length
      : null;

  const ranked = [...courses].sort(
    (a, b) => (b.health_score ?? -1) - (a.health_score ?? -1),
  );

  return (
    <div className="space-y-20">
      <section className="max-w-4xl">
        <span
          className="micro-cap inline-block rounded-[var(--radius-full)] px-3 py-1.5"
          style={{ backgroundColor: "var(--color-block-butter)" }}
        >
          Curriculum audit
        </span>
        <h1 className="display-xl mt-6 text-[var(--color-ink)]">
          Where the syllabus and the job market diverge
        </h1>
        <p className="body-lg mt-6 max-w-2xl text-[var(--color-ink-soft)]">
          Every course below has been compared against real job postings through
          a shared skill ontology. Each is scored against demand in its own
          subject area rather than the whole tech market, since one course
          covering a small share of all demand is normal and says nothing
          useful.
        </p>
      </section>

      <section className="grid gap-6 lg:grid-cols-4">
        <Card block="var(--color-block-periwinkle)" className="lg:col-span-1">
          <p className="micro-cap text-[var(--color-ink)]">Program alignment</p>
          <div className="mt-4">
            <HealthScore score={programAlignment} />
          </div>
          <p className="caption mt-3 text-[var(--color-ink-soft)]">
            mean across {scored.length}{" "}
            {scored.length === 1 ? "course" : "courses"}
          </p>
        </Card>

        <Card className="lg:col-span-3">
          <div className="grid gap-8 sm:grid-cols-3">
            <Stat
              label="Postings analysed"
              value={market?.postings ?? 0}
              hint={
                market?.earliest && market?.latest
                  ? `${market.earliest} to ${market.latest}`
                  : undefined
              }
            />
            <Stat
              label="Skills demanded"
              value={market?.skills_demanded ?? 0}
              hint={`${market?.demands ?? 0} requirements extracted`}
            />
            <Stat
              label="Courses audited"
              value={courses.length}
              hint={`${courses.reduce((n, c) => n + c.gap_count, 0)} gaps identified`}
            />
          </div>
        </Card>
      </section>

      <section>
        <SectionTitle hint="Ranked by how well each course covers demand in its own field. Select one to see its gaps and the evidence behind them.">
          Courses
        </SectionTitle>

        {courses.length === 0 ? (
          <EmptyState
            title="No courses ingested yet"
            body="Run the seed script to populate the database, or upload a syllabus to analyse it directly."
          />
        ) : (
          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)]">
            <table className="w-full">
              <thead>
                <tr style={{ backgroundColor: "var(--color-surface-soft)" }}>
                  <th className="micro-cap px-6 py-4 text-left text-[var(--color-ink-mute)]">
                    Course
                  </th>
                  <th className="micro-cap px-6 py-4 text-right text-[var(--color-ink-mute)]">
                    Teaches
                  </th>
                  <th className="micro-cap px-6 py-4 text-right text-[var(--color-ink-mute)]">
                    Gaps
                  </th>
                  <th className="micro-cap px-6 py-4 text-right text-[var(--color-ink-mute)]">
                    Alignment
                  </th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((course) => (
                  <tr
                    key={course.code}
                    className="border-t border-[var(--color-hairline)] transition-colors hover:bg-[var(--color-surface-soft)]"
                  >
                    <td className="px-6 py-5">
                      <Link
                        href={`/courses/${encodeURIComponent(course.code)}`}
                        className="block"
                      >
                        <span className="card-title text-[var(--color-ink)]">
                          {course.title}
                        </span>
                        <span className="tabular caption mt-1 block text-[var(--color-ink-mute)]">
                          {course.code}
                        </span>
                      </Link>
                    </td>
                    <td className="tabular px-6 py-5 text-right text-[16px] text-[var(--color-ink-soft)]">
                      {course.skills_taught}
                    </td>
                    <td className="tabular px-6 py-5 text-right text-[16px] text-[var(--color-ink-soft)]">
                      {course.gap_count}
                    </td>
                    <td className="px-6 py-5 text-right">
                      <HealthScore score={course.health_score} size="small" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <SectionTitle>Reading the alignment score</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-3">
          <Card block="var(--color-block-sage)">
            <p className="tabular display-md">60 to 100</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              Strong coverage of its own subject area. Remaining gaps are
              specialised.
            </p>
          </Card>
          <Card block="var(--color-block-butter)">
            <p className="tabular display-md">30 to 60</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              Meaningful drift. Several in-demand skills in this field are
              uncovered but reachable.
            </p>
          </Card>
          <Card block="var(--color-block-orchid)">
            <p className="tabular display-md">Below 30</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              Substantial misalignment. Skills core to this subject area are
              absent from the syllabus.
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}
