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
  const programHealth =
    scored.length > 0
      ? scored.reduce((sum, course) => sum + (course.health_score ?? 0), 0) /
        scored.length
      : null;

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
          Curriculum Health
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          Every course below has been compared against real job postings through
          a shared skill ontology. The score reflects how much current market
          demand the curriculum covers, weighted by how far each missing skill
          sits from what is already taught.
        </p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-wider text-slate-500">
            Program health
          </p>
          <div className="mt-2">
            <HealthScore score={programHealth} />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            mean across {scored.length}{" "}
            {scored.length === 1 ? "course" : "courses"}
          </p>
        </Card>

        <Card>
          <Stat
            label="Job postings analysed"
            value={market?.postings ?? 0}
            hint={
              market?.earliest && market?.latest
                ? `${market.earliest} to ${market.latest}`
                : undefined
            }
          />
        </Card>

        <Card>
          <Stat
            label="Distinct skills demanded"
            value={market?.skills_demanded ?? 0}
            hint={`${market?.demands ?? 0} skill requirements extracted`}
          />
        </Card>

        <Card>
          <Stat
            label="Courses audited"
            value={courses.length}
            hint={`${courses.reduce((n, c) => n + c.gap_count, 0)} gaps identified`}
          />
        </Card>
      </div>

      <section>
        <SectionTitle hint="Select a course to see its ranked gaps and the evidence behind each one.">
          Courses
        </SectionTitle>

        {courses.length === 0 ? (
          <EmptyState
            title="No courses ingested yet"
            body="Run the seed script to populate the database, or upload a syllabus to analyse it directly."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {courses.map((course) => (
              <Link
                key={course.code}
                href={`/courses/${encodeURIComponent(course.code)}`}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 transition-colors hover:border-slate-700 hover:bg-slate-900/70"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">
                      {course.title}
                    </p>
                    <p className="mt-0.5 truncate font-mono text-xs text-slate-500">
                      {course.code}
                    </p>
                  </div>
                  <HealthScore score={course.health_score} size="small" />
                </div>

                <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-800 pt-3 text-xs">
                  <div>
                    <dt className="text-slate-500">Teaches</dt>
                    <dd className="mt-0.5 font-mono text-slate-300">
                      {course.skills_taught}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Gaps</dt>
                    <dd className="mt-0.5 font-mono text-slate-300">
                      {course.gap_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Critical</dt>
                    <dd className="mt-0.5 font-mono text-rose-400">
                      {course.critical_gaps}
                    </dd>
                  </div>
                </dl>
              </Link>
            ))}
          </div>
        )}
      </section>

      <Card className="bg-slate-900/20">
        <SectionTitle>How to read the score</SectionTitle>
        <div className="grid gap-4 text-sm text-slate-400 sm:grid-cols-3">
          <p>
            <span className="font-mono text-emerald-400">70 to 100</span>
            <br />
            Curriculum broadly tracks market demand. Remaining gaps are
            specialised.
          </p>
          <p>
            <span className="font-mono text-amber-400">40 to 70</span>
            <br />
            Meaningful drift. Several in-demand skills are uncovered but
            reachable.
          </p>
          <p>
            <span className="font-mono text-rose-400">Below 40</span>
            <br />
            Substantial misalignment. Core market skills are absent from the
            syllabus.
          </p>
        </div>
      </Card>
    </div>
  );
}
