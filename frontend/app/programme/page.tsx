import Link from "next/link";

import { api, type ProgrammeReport, type ComplianceFindings } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";
import { Card, ErrorPanel, SectionTitle, Stat } from "@/components/ui";

export const dynamic = "force-dynamic";

const SEVERITY_TONE: Record<string, string> = {
  major: "var(--color-block-orchid)",
  risk: "var(--color-block-butter)",
  observation: "var(--color-block-stone)",
};

export default async function ProgrammePage() {
  let report: ProgrammeReport | null = null;
  let findings: ComplianceFindings | null = null;
  let error: string | null = null;

  try {
    [report, findings] = await Promise.all([
      api.programme(20),
      api.complianceFindings(),
    ]);
  } catch (exception) {
    error = exception instanceof Error ? exception.message : String(exception);
  }

  if (error || !report) return <ErrorPanel message={error ?? "No data"} />;

  return (
    <div className="space-y-20">
      <section className="max-w-3xl">
        <h1 className="display-lg text-[var(--color-ink)]">
          The whole degree, not one course
        </h1>
        <p className="body-lg mt-5 text-[var(--color-ink-soft)]">
          A gap in one syllabus may be covered elsewhere in the programme. These
          are the skills no course teaches at all, each with the course best
          placed to take it on and what that would cost.
        </p>
      </section>

      {/* Accreditation status first: it is the finding with consequences. */}
      {findings ? (
        <section className="grid gap-6 lg:grid-cols-4">
          <Card
            block={
              findings.major_count > 0
                ? "var(--color-block-orchid)"
                : "var(--color-block-sage)"
            }
          >
            <p className="micro-cap text-[var(--color-ink)]">NBA outcomes</p>
            <p className="tabular mt-3 text-[40px] font-light leading-none">
              {findings.pos_covered}
              <span className="text-[20px] text-[var(--color-ink-soft)]">
                /{findings.pos_total}
              </span>
            </p>
            <p className="caption mt-2 text-[var(--color-ink-soft)]">
              programme outcomes evidenced
            </p>
          </Card>

          <Card className="lg:col-span-3">
            <div className="grid gap-8 sm:grid-cols-3">
              <Stat
                label="Programme gaps"
                value={report.gap_count}
                hint="taught by no course"
              />
              <Stat
                label="Structural defects"
                value={report.defect_count}
                hint="taught without prerequisites"
              />
              <Stat
                label="Outcomes mapped"
                value={findings.outcomes_mapped}
                hint="course outcomes to NBA POs"
              />
            </div>
          </Card>
        </section>
      ) : null}

      {findings && findings.findings.length > 0 ? (
        <section>
          <SectionTitle hint="What an accreditation assessor would raise, ordered by how seriously a panel treats it.">
            Compliance findings
          </SectionTitle>
          <div className="space-y-3">
            {findings.findings.slice(0, 6).map((finding) => (
              <div
                key={`${finding.po}-${finding.severity}`}
                className="flex flex-wrap items-baseline gap-x-4 gap-y-2 rounded-[var(--radius-md)] border border-[var(--color-hairline)] px-6 py-4"
                style={{ backgroundColor: SEVERITY_TONE[finding.severity] }}
              >
                <span className="micro-cap shrink-0">{finding.severity}</span>
                <span className="tabular shrink-0 font-medium">{finding.po}</span>
                <span className="text-[15px] text-[var(--color-ink-soft)]">
                  {finding.finding}
                </span>
                <span className="caption w-full text-[var(--color-ink-mute)]">
                  {finding.statement}
                </span>
              </div>
            ))}
          </div>
          <p className="caption mt-4 text-[var(--color-ink-mute)]">
            Mapping is derived from the skill graph and capped by match
            confidence. It does not claim attainment, which requires assessment
            results.
          </p>
        </section>
      ) : null}

      <section>
        <SectionTitle hint="Skills no course in the programme teaches, with the course best placed to host each one.">
          Programme-wide gaps
        </SectionTitle>

        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)]">
          {report.gaps.map((gap, index) => {
            const block = categoryBlock(gap.category);
            const placement = gap.placement;

            return (
              <div
                key={gap.skill}
                className={`flex flex-wrap items-baseline gap-x-5 gap-y-2 bg-[var(--color-surface)] px-6 py-4 ${
                  index === report!.gaps.length - 1
                    ? ""
                    : "border-b border-[var(--color-hairline)]"
                }`}
              >
                <span
                  aria-hidden
                  className="h-2.5 w-2.5 shrink-0 self-center rounded-full"
                  style={{ backgroundColor: block.dot }}
                />
                <span className="min-w-[11rem] text-[16px] font-medium text-[var(--color-ink)]">
                  {gap.skill}
                </span>
                <span className="tabular caption shrink-0 text-[var(--color-ink-mute)]">
                  {gap.postings_requiring} of {gap.postings_total}
                </span>

                {placement?.course_code ? (
                  <span className="caption text-[var(--color-ink-soft)]">
                    teach in{" "}
                    <Link
                      href={`/courses/${encodeURIComponent(placement.course_code)}`}
                      className="font-medium text-[var(--color-ink)] underline underline-offset-2"
                    >
                      {placement.course_code.replace(/_/g, " ").slice(0, 34)}
                    </Link>
                    {placement.alternatives?.length
                      ? ` (${placement.alternatives.length} equally close)`
                      : ""}
                  </span>
                ) : (
                  <span className="caption text-[var(--color-severity-critical)]">
                    no course is close enough to host this
                  </span>
                )}

                <span className="micro-cap ml-auto shrink-0 text-[var(--color-ink-mute)]">
                  {placement?.effort ?? "unknown"}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {report.structural_defects.length > 0 ? (
        <section>
          <SectionTitle hint="Skills the curriculum teaches whose prerequisites nothing in the programme covers. Students are being asked to absorb material they have no foundation for.">
            Structural defects
          </SectionTitle>
          <div className="grid gap-4 md:grid-cols-2">
            {report.structural_defects.slice(0, 8).map((defect) => (
              <div
                key={defect.skill}
                className="rounded-[var(--radius-md)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-5"
              >
                <p className="card-title text-[var(--color-ink)]">
                  {defect.skill}
                </p>
                <p className="mt-2 text-[15px] text-[var(--color-ink-soft)]">
                  needs{" "}
                  <span className="font-medium text-[var(--color-severity-high)]">
                    {defect.missing_prerequisites.slice(0, 3).join(", ")}
                  </span>
                  , which no course teaches
                </p>
                <p className="caption mt-2 text-[var(--color-ink-mute)]">
                  taught in {defect.taught_in.slice(0, 2).join(", ")}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
