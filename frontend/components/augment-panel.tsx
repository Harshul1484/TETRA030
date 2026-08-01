"use client";

import { useState } from "react";

import { api, type AugmentProposal } from "@/lib/api";

interface Section {
  key: keyof Pick<
    AugmentProposal,
    "added_outcomes" | "case_studies" | "toolsets" | "project_prompts"
  >;
  title: string;
  hint: string;
}

const SECTIONS: Section[] = [
  {
    key: "added_outcomes",
    title: "New course outcomes",
    hint: "Phrased to drop into the existing outcomes list",
  },
  {
    key: "toolsets",
    title: "Tools to introduce",
    hint: "Each mapped to an existing unit",
  },
  {
    key: "case_studies",
    title: "Case studies",
    hint: "For discussion in an existing lecture slot",
  },
  {
    key: "project_prompts",
    title: "Project briefs",
    hint: "Each closes several gaps at once",
  },
];

export function AugmentPanel({ courseCode }: { courseCode: string }) {
  const [proposal, setProposal] = useState<AugmentProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setProposal(await api.augment(courseCode));
    } catch (exception) {
      setError(
        exception instanceof Error ? exception.message : String(exception),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!proposal) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-center">
        <p className="mx-auto max-w-lg text-sm text-slate-400">
          Generate targeted additions that close the gaps above without
          redesigning the course. Proposals extend existing units and cite the
          market evidence behind each change.
        </p>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="mt-4 rounded-lg border border-sky-500/40 bg-sky-500/10 px-5 py-2.5 text-sm font-medium text-sky-300 transition-colors hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Generating proposals..." : "Generate modifications"}
        </button>
        {loading ? (
          <p className="mt-3 text-xs text-slate-500">
            Reading the gap report and the course subgraph. This takes a few
            seconds.
          </p>
        ) : null}
        {error ? (
          <p className="mt-3 text-xs text-rose-400">{error}</p>
        ) : null}
      </div>
    );
  }

  const empty = SECTIONS.every((section) => proposal[section.key].length === 0);

  return (
    <div className="space-y-4">
      {empty ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
          <p className="text-sm text-amber-300">
            No proposals were generated.
          </p>
          <p className="mt-1 text-sm text-slate-400">{proposal.rationale}</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {SECTIONS.map((section) => {
              const items = proposal[section.key];
              if (items.length === 0) return null;
              return (
                <div
                  key={section.key}
                  className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5"
                >
                  <h3 className="text-sm font-semibold text-slate-100">
                    {section.title}
                  </h3>
                  <p className="mt-0.5 text-xs text-slate-500">{section.hint}</p>
                  <ul className="mt-3 space-y-2.5">
                    {items.map((item, index) => (
                      <li
                        key={index}
                        className="flex gap-2.5 text-sm leading-relaxed text-slate-300"
                      >
                        <span
                          aria-hidden
                          className="mt-0.5 shrink-0 font-mono text-xs text-emerald-500"
                        >
                          +
                        </span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-sm font-semibold text-slate-100">
              Rationale for the curriculum committee
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              {proposal.rationale}
            </p>
          </div>
        </>
      )}

      <button
        type="button"
        onClick={generate}
        disabled={loading}
        className="text-xs text-slate-500 transition-colors hover:text-slate-300 disabled:opacity-60"
      >
        {loading ? "Regenerating..." : "Regenerate"}
      </button>
    </div>
  );
}
