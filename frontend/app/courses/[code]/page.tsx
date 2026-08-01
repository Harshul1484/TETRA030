import Link from "next/link";

import { api, type GapReport } from "@/lib/api";
import { AugmentPanel } from "@/components/augment-panel";
import { GapList } from "@/components/gap-list";
import { Card, ErrorPanel, HealthScore, SectionTitle, Stat } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function CoursePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const courseCode = decodeURIComponent(code);

  let report: GapReport | null = null;
  let error: string | null = null;

  try {
    report = await api.gaps(courseCode);
  } catch (exception) {
    error = exception instanceof Error ? exception.message : String(exception);
  }

  if (error || !report) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-100">
          Back to dashboard
        </Link>
        <ErrorPanel message={error ?? "Course not found"} />
      </div>
    );
  }

  const critical = report.gaps.filter((gap) => gap.severity === "critical").length;
  const reachable = report.gaps.filter(
    (gap) => gap.prerequisite_distance <= 2,
  ).length;
  const covered = report.gaps.filter((gap) => gap.curriculum_coverage > 0).length;

  return (
    <div className="space-y-8">
      <div>
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-100">
          Back to dashboard
        </Link>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">
          {report.course_title}
        </h1>
        <p className="mt-1 font-mono text-xs text-slate-500">
          {report.course_code}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-wider text-slate-500">
            Curriculum health
          </p>
          <div className="mt-2">
            <HealthScore score={report.health_score} />
          </div>
        </Card>
        <Card>
          <Stat label="Gaps identified" value={report.gaps.length} />
        </Card>
        <Card>
          <Stat
            label="Critical"
            value={critical}
            hint="high demand, no coverage"
          />
        </Card>
        <Card>
          <Stat
            label="Low-cost additions"
            value={reachable}
            hint="within two prerequisite hops"
          />
        </Card>
      </div>

      <section>
        <SectionTitle hint="Ranked by market demand weighted against current coverage. Every gap cites the postings behind it.">
          Skill gaps
        </SectionTitle>
        <GapList gaps={report.gaps} />
      </section>

      <section>
        <SectionTitle hint="Generated from the gaps above. Proposals extend existing units rather than replacing the course.">
          Proposed syllabus modifications
        </SectionTitle>
        <AugmentPanel courseCode={report.course_code} />
      </section>

      {covered > 0 ? (
        <p className="text-xs text-slate-500">
          {covered} of these skills already have partial coverage in the
          syllabus. They remain listed because market demand exceeds the depth
          currently taught.
        </p>
      ) : null}
    </div>
  );
}
