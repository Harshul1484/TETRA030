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
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-canvas-soft)] p-8 text-center">
        <p className="mx-auto max-w-lg text-[15px] leading-relaxed text-[var(--color-ink-secondary)]">
          Generate targeted additions that close the gaps above without
          redesigning the course. Proposals extend existing units and cite the
          market evidence behind each change.
        </p>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="mt-5 inline-flex min-h-[40px] items-center rounded-full bg-[var(--color-primary)] px-4 py-2 text-[16px] font-normal text-white transition-colors hover:bg-[var(--color-primary-deep)] active:bg-[var(--color-primary-press)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Generating proposals..." : "Generate modifications"}
        </button>
        {loading ? (
          <p className="caption mt-3 text-[var(--color-ink-mute)]">
            Reading the gap report and the course subgraph. This takes a few
            seconds.
          </p>
        ) : null}
        {error ? (
          <p className="caption mt-3 text-[var(--color-severity-critical)]">{error}</p>
        ) : null}
      </div>
    );
  }

  const empty = SECTIONS.every((section) => proposal[section.key].length === 0);

  return (
    <div className="space-y-4">
      {empty ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-severity-high)]/25 bg-[var(--color-canvas-cream)] p-6">
          <p className="heading-sm text-[var(--color-severity-high)]">
            No proposals were generated.
          </p>
          <p className="mt-2 text-[15px] text-[var(--color-ink-secondary)]">{proposal.rationale}</p>
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
                  className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-white p-6"
                >
                  <h3 className="heading-sm text-[var(--color-ink)]">
                    {section.title}
                  </h3>
                  <p className="caption mt-1 text-[var(--color-ink-mute)]">{section.hint}</p>
                  <ul className="mt-4 space-y-3">
                    {items.map((item, index) => (
                      <li
                        key={index}
                        className="flex gap-3 text-[15px] leading-relaxed text-[var(--color-ink-secondary)]"
                      >
                        <span
                          aria-hidden
                          className="mt-0.5 shrink-0 font-mono text-[13px] text-[var(--color-positive)]"
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

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-canvas-soft)] p-6">
            <h3 className="heading-sm text-[var(--color-ink)]">
              Rationale for the curriculum committee
            </h3>
            <p className="mt-3 text-[15px] leading-relaxed text-[var(--color-ink-secondary)]">
              {proposal.rationale}
            </p>
          </div>
        </>
      )}

      <button
        type="button"
        onClick={generate}
        disabled={loading}
        className="caption text-[var(--color-ink-mute)] transition-colors hover:text-[var(--color-primary)] disabled:opacity-50"
      >
        {loading ? "Regenerating..." : "Regenerate"}
      </button>
    </div>
  );
}
