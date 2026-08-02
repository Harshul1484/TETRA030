"use client";

import { useState } from "react";

import type { SkillGap } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";
import { Button, SeverityBadge } from "@/components/ui";

const UNREACHABLE = 99;
const INITIAL_VISIBLE = 8;

/** The cost framing is the product's differentiator, so it gets its own row. */
function reachability(distance: number): {
  label: string;
  detail: string;
  tone: string;
} {
  if (distance <= 1) {
    return {
      label: "Low cost",
      detail: "adjacent to what this course already teaches",
      tone: "text-[var(--color-success)]",
    };
  }
  if (distance >= UNREACHABLE) {
    return {
      label: "No path",
      detail: "nothing in this course leads toward it",
      tone: "text-[var(--color-severity-critical)]",
    };
  }
  return {
    label: `${distance} steps`,
    detail: "of prerequisites before this can be taught",
    tone: "text-[var(--color-severity-high)]",
  };
}

export function GapList({
  gaps,
  evidenceThin = false,
}: {
  gaps: SkillGap[];
  evidenceThin?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  if (gaps.length === 0) {
    // An empty list means two opposite things: full coverage, or an audit
    // that declined to answer. Reporting the second as the first would tell a
    // professor their course is aligned to a market nobody measured.
    return (
      <div
        className="rounded-[var(--radius-lg)] p-8 text-[16px]"
        style={{
          backgroundColor: evidenceThin
            ? "var(--color-surface-soft)"
            : "var(--color-block-sage)",
        }}
      >
        {evidenceThin
          ? "No findings reported. The corpus does not hold enough postings in this subject area to identify gaps, as described above."
          : "No gaps found. This curriculum covers the analysed market demand."}
      </div>
    );
  }

  const visible = expanded ? gaps : gaps.slice(0, INITIAL_VISIBLE);

  return (
    <div>
      <div className="grid gap-4 md:grid-cols-2">
        {visible.map((gap) => {
          const reach = reachability(gap.prerequisite_distance);
          const block = categoryBlock(gap.category);
          const share = Math.round(gap.market_demand * 100);

          return (
            <article
              key={gap.canonical_skill}
              className="flex flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] transition-colors hover:border-[var(--color-ink)]"
            >
              {/* The demand figure is the reason a gap matters, so it is the
                  largest thing on the card and sits in its category colour. */}
              <div
                className="flex items-start justify-between gap-4 px-6 py-5"
                style={{ backgroundColor: block.bg }}
              >
                <div className="min-w-0">
                  <h3 className="card-title text-[var(--color-ink)]">
                    {gap.canonical_skill}
                  </h3>
                  <p className="micro-cap mt-1.5 text-[var(--color-ink-soft)]">
                    {block.label}
                  </p>
                </div>

                <div className="shrink-0 text-right">
                  <p className="tabular text-[34px] font-light leading-none text-[var(--color-ink)]">
                    {share}
                    <span className="text-[18px] text-[var(--color-ink-soft)]">
                      %
                    </span>
                  </p>
                  <p className="micro-cap mt-1 text-[var(--color-ink-soft)]">
                    of postings
                  </p>
                </div>
              </div>

              <div className="flex flex-1 flex-col gap-4 px-6 py-5">
                <p className="text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
                  <span className="tabular font-medium text-[var(--color-ink)]">
                    {gap.postings_requiring} of {gap.postings_total}
                  </span>{" "}
                  postings require this
                  {gap.curriculum_coverage > 0
                    ? `, and the syllabus covers it only partially`
                    : `, and no outcome in this course covers it`}
                  .
                </p>

                <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-[var(--color-hairline)] pt-4">
                  <SeverityBadge severity={gap.severity} />
                  <span className={`caption font-semibold ${reach.tone}`}>
                    {reach.label}
                  </span>
                  <span className="caption text-[var(--color-ink-mute)]">
                    {reach.detail}
                  </span>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {gaps.length > INITIAL_VISIBLE ? (
        <div className="mt-8">
          <Button variant="secondary" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show fewer" : `Show all ${gaps.length} gaps`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
