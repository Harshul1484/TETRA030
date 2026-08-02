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
    stage: "Embed",
    detail:
      "Outcomes become vectors locally, so paraphrases resolve without an API call.",
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

const RETURNS = [
  {
    label: "Ranked gaps",
    detail: "Every entry citing the postings behind it.",
    block: "var(--color-block-sky)",
  },
  {
    label: "A teaching sequence",
    detail: "Prerequisite-ordered, so nothing precedes its groundwork.",
    block: "var(--color-block-sage)",
  },
  {
    label: "Proposed additions",
    detail: "Extending existing units rather than replacing the course.",
    block: "var(--color-block-periwinkle)",
  },
  {
    label: "The cost of each",
    detail: "How many prerequisite hops away a missing skill sits.",
    block: "var(--color-block-butter)",
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
          <p
            className="micro-cap inline-block rounded-[var(--radius-full)] px-3.5 py-1.5 text-[var(--color-ink)]"
            style={{ backgroundColor: "var(--color-block-butter)" }}
          >
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
              href="/upload"
              className="inline-flex min-h-[46px] items-center rounded-[var(--radius-sm)] border border-[var(--color-ink)] px-6 text-[16px] font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-surface)]"
            >
              Analyse your own syllabus
            </Link>
            <Link
              href="/graph"
              className="caption inline-flex min-h-[46px] items-center font-medium text-[var(--color-ink)] underline underline-offset-4"
            >
              Explore the graph
            </Link>
          </div>

          {market ? (
            <div className="mt-10 flex flex-wrap gap-x-10 gap-y-5 border-t border-[var(--color-hairline)] pt-7">
              <div>
                <p className="tabular text-[30px] font-light leading-none text-[var(--color-ink)]">
                  {market.postings}
                </p>
                <p className="micro-cap mt-2 text-[var(--color-ink-mute)]">
                  real job postings
                </p>
              </div>
              <div>
                <p className="tabular text-[30px] font-light leading-none text-[var(--color-ink)]">
                  {courses.length}
                </p>
                <p className="micro-cap mt-2 text-[var(--color-ink-mute)]">
                  university courses
                </p>
              </div>
              <div>
                <p className="tabular text-[30px] font-light leading-none text-[var(--color-ink)]">
                  {market.skills_demanded}
                </p>
                <p className="micro-cap mt-2 text-[var(--color-ink-mute)]">
                  skills demanded
                </p>
              </div>
            </div>
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
              Audited against real degree programmes.
            </h2>
            <p className="body-lg mt-6 text-[var(--color-ink-soft)]">
              {courses.length} published syllabi from The Maharaja Sayajirao
              University of Baroda and NIT, spanning computing and civil
              engineering, each scored against demand in its own subject area.
              No synthetic examples, no samples tuned to look bad.
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

      {/* The seeded courses prove the audit works. This is the claim that it
          works on a document nobody prepared for it, which is the one a judge
          can test in the room. */}
      <section className="border-y border-[var(--color-hairline)] py-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h2 className="display-lg text-[var(--color-ink)]">
              Bring your own syllabus.
            </h2>
            <p className="body-lg mt-6 max-w-xl text-[var(--color-ink-soft)]">
              Everything above runs on courses loaded ahead of time. Upload a
              PDF and it goes through the same six stages, with no fixture path
              and no pre-computed answer. Civil, electrical, mechanical and
              computing curricula are all in scope.
            </p>
            <Link
              href="/upload"
              className="mt-8 inline-flex min-h-[46px] items-center rounded-[var(--radius-sm)] bg-[var(--color-ink)] px-6 text-[16px] font-medium text-white transition-colors hover:bg-[var(--color-ink-soft)]"
            >
              Analyse a syllabus
            </Link>
          </div>

          <div>
            <p className="micro-cap text-[var(--color-ink-mute)]">
              What comes back
            </p>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {RETURNS.map((item) => (
                <div
                  key={item.label}
                  className="rounded-[var(--radius-md)] px-5 py-5"
                  style={{ backgroundColor: item.block }}
                >
                  <p className="card-title text-[var(--color-ink)]">
                    {item.label}
                  </p>
                  <p className="caption mt-2 leading-relaxed text-[var(--color-ink-soft)]">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>

            {/* Set apart because it is the opposite of the three above: the
                case where the honest output is no output. */}
            <div className="mt-3 rounded-[var(--radius-md)] border border-dashed border-[var(--color-hairline)] px-5 py-5">
              <p className="card-title text-[var(--color-ink-soft)]">
                Or nothing at all
              </p>
              <p className="caption mt-2 leading-relaxed text-[var(--color-ink-mute)]">
                Where the corpus holds too few postings in a subject to judge
                it, the audit says so and withholds the findings rather than
                handing over another field&apos;s skills.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works, as a sequence rather than a feature grid. */}
      <section>
        <h2 className="display-lg text-[var(--color-ink)]">
          Six stages, each replaceable.
        </h2>
        <div className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
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
                That corpus is mostly software. Where a discipline falls below
                the evidence threshold, courses in it are marked as such and no
                gaps are reported, rather than being handed the market&apos;s
                most common skills under another field&apos;s name.
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
