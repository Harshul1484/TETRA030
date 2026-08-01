"use client";

import { useState } from "react";

import type { SkillGap } from "@/lib/api";
import { DemandBar, SeverityBadge } from "@/components/ui";

const UNREACHABLE = 99;
const INITIAL_VISIBLE = 12;

/** The cost framing is the product's differentiator, so it gets its own line. */
function reachabilityLabel(distance: number): { text: string; tone: string } {
  if (distance <= 1) {
    return {
      text: "Adjacent to existing content, low-cost addition",
      tone: "text-emerald-400",
    };
  }
  if (distance >= UNREACHABLE) {
    return {
      text: "No prerequisite path from current content",
      tone: "text-rose-400",
    };
  }
  return {
    text: `${distance} prerequisite hops from existing content`,
    tone: "text-amber-400",
  };
}

export function GapList({ gaps }: { gaps: SkillGap[] }) {
  const [expanded, setExpanded] = useState(false);

  if (gaps.length === 0) {
    return (
      <p className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-sm text-slate-400">
        No gaps found. This curriculum covers the analysed market demand.
      </p>
    );
  }

  const visible = expanded ? gaps : gaps.slice(0, INITIAL_VISIBLE);

  return (
    <div className="space-y-3">
      {visible.map((gap) => {
        const reach = reachabilityLabel(gap.prerequisite_distance);
        return (
          <article
            key={gap.canonical_skill}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition-colors hover:border-slate-700"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-medium text-slate-100">
                    {gap.canonical_skill}
                  </h3>
                  <SeverityBadge severity={gap.severity} />
                  {gap.curriculum_coverage > 0 ? (
                    <span className="rounded border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-sky-300">
                      partly covered
                    </span>
                  ) : null}
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                  {gap.evidence}
                </p>
                <p className={`mt-1 text-xs ${reach.tone}`}>{reach.text}</p>
              </div>

              <div className="w-32 shrink-0">
                <p className="text-right font-mono text-xs text-slate-400">
                  {gap.postings_requiring}
                  <span className="text-slate-600">
                    {" / "}
                    {gap.postings_total}
                  </span>
                </p>
                <div className="mt-1.5">
                  <DemandBar value={gap.market_demand} />
                </div>
                <p className="mt-1 text-right text-[10px] uppercase tracking-wider text-slate-600">
                  market demand
                </p>
              </div>
            </div>
          </article>
        );
      })}

      {gaps.length > INITIAL_VISIBLE ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full rounded-lg border border-slate-800 bg-slate-900/40 py-2.5 text-sm text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-200"
        >
          {expanded
            ? "Show fewer"
            : `Show all ${gaps.length} gaps`}
        </button>
      ) : null}
    </div>
  );
}
