import Link from "next/link";

import { api, type CourseSummary, type MarketSummary } from "@/lib/api";
import { HeroReport } from "@/components/hero-report";

export const dynamic = "force-dynamic";

const PIPELINE = [
  {
    stage: "Ingest",
    detail: "Syllabus PDFs and a committed corpus of real job postings.",
  },
  {
    stage: "Extract",
    detail:
      "Claude identifies skills, constrained to a curated taxonomy so it cannot invent them.",
  },
  {
    stage: "Match",
    detail:
      "Exact alias resolution first, then vector similarity for the paraphrases.",
  },
  {
    stage: "Score",
    detail:
      "A graph traversal measures demand, coverage, and prerequisite distance.",
  },
  {
    stage: "Augment",
    detail:
      "Claude proposes additions that extend existing units rather than replacing them.",
  },
];

export default async function LandingPage() {
  let courses: CourseSummary[] = [];
  let market: MarketSummary | null = null;

  try {
    [courses, market] = await Promise.all([api.courses(), api.marketSummary()]);
  } catch {
    // The landing page reads fine without live numbers, so a cold API
    // degrades to the static copy rather than an error screen.
  }

  const ranked = [...courses]
    .filter((course) => course.health_score !== null)
    .sort((a, b) => (b.health_score ?? 0) - (a.health_score ?? 0));

  return (
    <div className="space-y-24">
      {/* Hero: the claim on the left, the product's real output on the right.
          A screenshot would be a drawing of the thing; this is the thing. */}
      <section className="grid items-start gap-14 pt-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div>
          <p className="micro-cap text-[var(--color-ink-mute)]">
            TetraTHON 2026 &middot; Track D
          </p>
          <h1 className="display-xl mt-5 text-[var(--color-ink)]">
            Your curriculum is three years behind. Here is the receipt.
          </h1>
          <p className="body-lg mt-7 max-w-xl text-[var(--color-ink-soft)]">
            Vedha reads a syllabus, compares it against live job postings
            through a shared skill ontology, and reports not just what is
            missing but what it would cost to teach.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="inline-flex min-h-[46px] items-center rounded-[var(--radius-sm)] bg-[var(--color-ink)] px-6 text-[16px] font-medium text-white transition-colors hover:bg-[var(--color-ink-soft)]"
            >
              See the audit
            </Link>
            <Link
              href="/graph"
              className="inline-flex min-h-[46px] items-center rounded-[var(--radius-sm)] border border-[var(--color-ink)] px-6 text-[16px] font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-surface)]"
            >
              Explore the graph
            </Link>
          </div>

          {market ? (
            <p className="caption mt-9 text-[var(--color-ink-mute)]">
              Analysing{" "}
              <span className="tabular font-medium text-[var(--color-ink)]">
                {market.postings}
              </span>{" "}
              real job postings against{" "}
              <span className="tabular font-medium text-[var(--color-ink)]">
                {courses.length}
              </span>{" "}
              university courses.
            </p>
          ) : null}
        </div>

        <HeroReport />
      </section>

      {/* The differentiator, stated once and plainly. */}
      <section className="border-y border-[var(--color-hairline)] py-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <h2 className="display-lg text-[var(--color-ink)]">
            Most tools tell you what is missing.
            <br />
            This one tells you what it costs.
          </h2>
          <div className="space-y-5">
            <p className="body-lg text-[var(--color-ink-soft)]">
              A keyword diff reports that a syllabus lacks Retrieval Augmented
              Generation. That is a complaint, not a plan.
            </p>
            <p className="body-lg text-[var(--color-ink-soft)]">
              Because the ontology records which skills are prerequisites for
              which, the answer becomes a sequence: Vector Databases and Large
              Language Models at one hop, Embeddings and Transformers at two,
              Deep Learning at three. Adding Kubernetes to a course that already
              teaches Docker is cheap. Adding RAG to a course covering none of
              its prerequisites is a different conversation.
            </p>
            <p className="caption text-[var(--color-ink-mute)]">
              That is also why the ontology is a graph rather than a table. It
              is a variable-length path search, which a relational schema
              answers only with a recursive query that degrades with every hop.
            </p>
          </div>
        </div>
      </section>

      {/* Evidence, drawn live from the running system. */}
      {ranked.length > 0 ? (
        <section className="grid gap-12 lg:grid-cols-2">
          <div>
            <h2 className="display-lg text-[var(--color-ink)]">
              Audited against a real degree programme.
            </h2>
            <p className="body-lg mt-6 text-[var(--color-ink-soft)]">
              Eight BCA course syllabi from The Maharaja Sayajirao University of
              Baroda, each scored against demand in its own subject area. No
              synthetic examples, no samples tuned to look bad.
            </p>
            <Link
              href="/dashboard"
              className="caption mt-6 inline-block font-medium text-[var(--color-ink)] underline underline-offset-4"
            >
              See every course
            </Link>
          </div>

          <div className="divide-y divide-[var(--color-hairline)] border-y border-[var(--color-hairline)]">
            {ranked.slice(0, 6).map((course) => (
              <Link
                key={course.code}
                href={`/courses/${encodeURIComponent(course.code)}`}
                className="flex items-baseline justify-between gap-6 py-4"
              >
                <span className="text-[16px] text-[var(--color-ink-soft)]">
                  {course.title.replace(/^BCA\d+\s*/, "")}
                </span>
                <span className="tabular shrink-0 text-[20px] font-medium text-[var(--color-ink)]">
                  {course.health_score?.toFixed(1)}
                </span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {/* How it works, as a sequence rather than a feature grid. */}
      <section>
        <h2 className="display-lg text-[var(--color-ink)]">
          Five stages, each replaceable.
        </h2>
        <div className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-5">
          {PIPELINE.map((step, index) => (
            <div key={step.stage}>
              <p className="tabular caption text-[var(--color-ink-mute)]">
                {String(index + 1).padStart(2, "0")}
              </p>
              <p className="card-title mt-2 text-[var(--color-ink)]">
                {step.stage}
              </p>
              <p className="caption mt-2 leading-relaxed text-[var(--color-ink-soft)]">
                {step.detail}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Closing on the limits. Stating them is itself a claim about rigour. */}
      <section className="border-t border-[var(--color-hairline)] pt-16">
        <div className="grid gap-10 lg:grid-cols-3">
          <h2 className="display-md text-[var(--color-ink)]">
            What it does not do
          </h2>
          <div className="lg:col-span-2">
            <ul className="space-y-4 text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
              <li>
                Embeddings do not encode negation, so &quot;finding patterns
                without labelled examples&quot; retrieves Supervised Learning.
                Exact taxonomy resolution runs first for exactly this reason.
              </li>
              <li>
                The job corpus spans about a month. Free APIs serve current
                listings only, so month-granularity trends work and a multi-year
                forecast does not.
              </li>
              <li>
                Scanned PDFs without a text layer are rejected rather than run
                through OCR.
              </li>
            </ul>
            <Link
              href="/about"
              className="caption mt-6 inline-block font-medium text-[var(--color-ink)] underline underline-offset-4"
            >
              Read the full method
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
