"use client";

import { useState } from "react";

import { api, type Roadmap as RoadmapData } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";
import { Button } from "@/components/ui";

/**
 * The gap report says what is missing. This says what to do about it.
 *
 * Stages come from a topological layering of the prerequisite graph, so a
 * skill never appears before something it depends on. That ordering is the
 * whole point: a list ranked by demand alone would schedule Amazon Web
 * Services before Cloud Computing.
 */
export function RoadmapPanel({ courseCode }: { courseCode: string }) {
  const [plan, setPlan] = useState<RoadmapData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setPlan(await api.roadmap(courseCode));
    } catch (exception) {
      setError(
        exception instanceof Error ? exception.message : String(exception),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!plan) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-8 text-center">
        <p className="mx-auto max-w-lg text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          Order the gaps into a teaching sequence. Skills are grouped into
          stages so that nothing is scheduled before the groundwork it depends
          on.
        </p>
        <div className="mt-6 flex justify-center">
          <Button onClick={generate} disabled={loading}>
            {loading ? "Building sequence..." : "Build teaching sequence"}
          </Button>
        </div>
        {error ? (
          <p className="caption mt-4 text-[var(--color-severity-critical)]">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  // Nothing to sequence is a legitimate outcome, not a failure: it follows
  // from a gap report that reported nothing. Left to the branch below it
  // rendered as an empty stage list under a sentence missing its numbers.
  if (plan.stages.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] bg-[var(--color-surface-soft)] p-8">
        <p className="text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          Nothing to schedule. A teaching sequence orders the gaps above, and
          none were reported for this course.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="caption text-[var(--color-ink-mute)]">
        {plan.total_skills} skills across {plan.stage_count}{" "}
        {plan.stage_count === 1 ? "stage" : "stages"}, ordered so no skill is
        taught before its prerequisites.
      </p>

      <div className="space-y-4">
        {plan.stages.map((stage) => (
          <div
            key={stage.stage}
            className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)]"
          >
            <div className="flex items-baseline gap-3 border-b border-[var(--color-hairline)] px-6 py-3.5">
              <span className="micro-cap text-[var(--color-ink-mute)]">
                Stage {stage.stage}
              </span>
              <span className="caption text-[var(--color-ink-mute)]">
                {stage.stage === 1
                  ? "can be taught immediately"
                  : `once stage ${stage.stage - 1} is in place`}
              </span>
            </div>

            <div className="divide-y divide-[var(--color-hairline)]">
              {stage.skills.map((entry) => {
                const block = categoryBlock(entry.category);
                const after = [
                  ...entry.covered_by_plan,
                  ...entry.already_taught,
                ];

                return (
                  <div
                    key={entry.skill}
                    className="flex flex-wrap items-baseline gap-x-4 gap-y-1.5 px-6 py-4"
                  >
                    <span
                      aria-hidden
                      className="h-2.5 w-2.5 shrink-0 self-center rounded-full"
                      style={{ backgroundColor: block.dot }}
                    />
                    <span className="text-[16px] font-medium text-[var(--color-ink)]">
                      {entry.skill}
                    </span>

                    {after.length > 0 ? (
                      <span className="caption text-[var(--color-ink-mute)]">
                        after {after.join(", ")}
                      </span>
                    ) : null}

                    {entry.outside_plan.length > 0 ? (
                      <span className="caption text-[var(--color-severity-high)]">
                        needs {entry.outside_plan.join(", ")} first, not in this
                        plan
                      </span>
                    ) : null}

                    <span className="tabular caption ml-auto shrink-0 text-[var(--color-ink-mute)]">
                      {entry.postings_requiring} of {entry.postings_total}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={generate}
        disabled={loading}
        className="caption text-[var(--color-ink-mute)] transition-colors hover:text-[var(--color-ink)] disabled:opacity-50"
      >
        {loading ? "Rebuilding..." : "Rebuild"}
      </button>
    </div>
  );
}
