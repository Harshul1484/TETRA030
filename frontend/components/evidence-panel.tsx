"use client";

import { useState } from "react";

import { api } from "@/lib/api";

/**
 * The postings a course was measured against.
 *
 * Every number in the gap report reduces to a count of job postings, which
 * the reader otherwise has to take on trust. This lists them, so a claim
 * that a subject area holds two postings can be checked rather than
 * believed. It matters most when the count is low enough that the audit
 * withholds its findings.
 */

interface Posting {
  title: string;
  source: string | null;
  url: string | null;
  posted_date: string | null;
  skills: string[];
}

interface Evidence {
  scored_against: string[];
  domain_postings: number;
  evidence_thin: boolean;
  postings: Posting[];
}

export function EvidencePanel({ courseCode }: { courseCode: string }) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setEvidence(await api.evidence(courseCode));
    } catch (exception) {
      setError(
        exception instanceof Error ? exception.message : String(exception),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!evidence) {
    return (
      <div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="caption font-medium text-[var(--color-ink)] underline underline-offset-4 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Loading postings..." : "Show the postings behind this"}
        </button>
        {error ? (
          <p className="caption mt-2 text-[var(--color-severity-critical)]">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  const subject = evidence.scored_against.join(", ");

  return (
    <div className="space-y-4">
      <p className="caption text-[var(--color-ink-mute)]">
        {evidence.postings.length === 0
          ? `No postings in this corpus demand ${subject} skills.`
          : `${evidence.domain_postings} postings in this corpus demand ${subject} skills. ${
              evidence.postings.length < evidence.domain_postings
                ? `Showing ${evidence.postings.length}.`
                : ""
            }`}
      </p>

      {evidence.postings.length > 0 ? (
        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)]">
          <div className="divide-y divide-[var(--color-hairline)]">
            {evidence.postings.map((posting, index) => (
              <div key={`${posting.title}-${index}`} className="px-5 py-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  {posting.url ? (
                    <a
                      href={posting.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[15px] font-medium text-[var(--color-ink)] underline underline-offset-4"
                    >
                      {posting.title}
                    </a>
                  ) : (
                    <span className="text-[15px] font-medium text-[var(--color-ink)]">
                      {posting.title}
                    </span>
                  )}
                  <span className="tabular caption shrink-0 text-[var(--color-ink-mute)]">
                    {posting.source}
                    {posting.posted_date ? ` · ${posting.posted_date}` : ""}
                  </span>
                </div>

                <p className="caption mt-2 text-[var(--color-ink-soft)]">
                  {posting.skills.join(", ")}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <p className="caption text-[var(--color-ink-mute)]">
        Postings from Arbeitnow and Remotive. Titles link to the original
        listing where the source provides one.
      </p>
    </div>
  );
}
