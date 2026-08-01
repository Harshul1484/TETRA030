import Link from "next/link";

import { api, type GapReport } from "@/lib/api";
import { AugmentPanel } from "@/components/augment-panel";
import { RoadmapPanel } from "@/components/roadmap";
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
        <Link href="/dashboard" className="caption text-[var(--color-ink-mute)] transition-colors hover:text-[var(--color-primary)]">
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
    <div className="space-y-12">
      <div>
        <Link href="/dashboard" className="caption text-[var(--color-ink-mute)] transition-colors hover:text-[var(--color-primary)]">
          Back to dashboard
        </Link>
        <h1 className="display-lg mt-4 text-[var(--color-ink)]">
          {report.course_title}
        </h1>
        <p className="tabular caption mt-1.5 text-[var(--color-ink-mute)]">
          {report.course_code}
        </p>
      </div>

      <div className="grid gap-6 border-y border-[var(--color-hairline)] py-8 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="micro-cap text-[var(--color-ink-mute)]">
            Domain alignment
          </p>
          <div className="mt-2">
            <HealthScore score={report.health_score} />
          </div>
          <p className="caption mt-3 leading-relaxed text-[var(--color-ink-mute)]">
            share of market demand in{" "}
            {report.scored_against?.length
              ? report.scored_against.join(" and ")
              : "this field"}{" "}
            that this syllabus covers
          </p>
        </div>
        <Stat label="Gaps identified" value={report.gaps.length} />
        <Stat
            label="Critical"
            value={critical}
            hint="high demand, no coverage"
          />
        <Stat
            label="Low-cost additions"
            value={reachable}
            hint="within two prerequisite hops"
          />
      </div>

      <section>
        <SectionTitle hint="Ranked by market demand weighted against current coverage. Every gap cites the postings behind it.">
          Skill gaps
        </SectionTitle>
        <GapList gaps={report.gaps} />
      </section>

      <section>
        <SectionTitle hint="Ordered by prerequisite dependency, so nothing is scheduled before the groundwork it needs. Derived from the graph, not from the syllabus text.">
          Teaching sequence
        </SectionTitle>
        <RoadmapPanel courseCode={report.course_code} />
      </section>

      <section>
        <SectionTitle hint="Generated from the gaps above. Proposals extend existing units rather than replacing the course.">
          Proposed syllabus modifications
        </SectionTitle>
        <AugmentPanel courseCode={report.course_code} />
      </section>

      {covered > 0 ? (
        <p className="caption text-[var(--color-ink-mute)]">
          {covered} of these skills already have partial coverage in the
          syllabus. They remain listed because market demand exceeds the depth
          currently taught.
        </p>
      ) : null}
    </div>
  );
}
