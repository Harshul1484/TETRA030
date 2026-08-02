import { SyllabusUpload } from "@/components/syllabus-upload";

export const metadata = {
  title: "Analyse a syllabus | Vedha",
};

const STEPS = [
  {
    title: "Parsed and read",
    detail:
      "Text is extracted in a temporary directory, which is deleted once parsing finishes. Only the outcomes are kept, never the file.",
    block: "var(--color-block-sky)",
  },
  {
    title: "Outcomes resolved to skills",
    detail:
      "Claude names the skills each outcome teaches, constrained to a taxonomy of 487 entries and 1,646 aliases so that “RCC design” and “reinforced concrete” land on one node and nothing outside the vocabulary can be invented.",
    block: "var(--color-block-periwinkle)",
  },
  {
    title: "Compared against live postings",
    detail:
      "Skills are matched against demand from real job postings and scored within the course’s own subject area, so a civil syllabus is judged on civil demand rather than the whole market.",
    block: "var(--color-block-sage)",
  },
  {
    title: "Returned as a plan",
    detail:
      "A ranked gap list with the postings behind each entry, a prerequisite-ordered teaching sequence, and proposed additions. Where the corpus lacks the evidence to judge a subject, it says so instead.",
    block: "var(--color-block-butter)",
  },
];

export default function UploadPage() {
  return (
    <div className="space-y-16">
      <section className="max-w-4xl">
        <h1 className="display-xl text-[var(--color-ink)]">
          Analyse your own syllabus
        </h1>
        <p className="body-lg mt-6 max-w-2xl text-[var(--color-ink-soft)]">
          The courses already loaded show what the audit produces. This runs it
          on a document you supply. Nothing is pre-computed: the file is parsed,
          its outcomes are extracted and embedded, and the resulting skills are
          scored against the same live job postings.
        </p>
      </section>

      <section>
        <SyllabusUpload />
      </section>

      <section className="border-t border-[var(--color-hairline)] pt-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <div>
            <h2 className="display-md text-[var(--color-ink)]">
              What happens to the file
            </h2>
            <p className="caption mt-4 max-w-xs leading-relaxed text-[var(--color-ink-mute)]">
              The same six stages every seeded course went through, in the same
              order, with no separate path for uploads.
            </p>
          </div>

          <ol className="space-y-px">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className="grid gap-x-6 gap-y-2 px-6 py-6 sm:grid-cols-[auto_minmax(0,1fr)]"
                style={{ backgroundColor: step.block }}
              >
                <p className="tabular text-[22px] font-light leading-none text-[var(--color-ink)]/55">
                  {String(index + 1).padStart(2, "0")}
                </p>
                <div>
                  <p className="card-title text-[var(--color-ink)]">
                    {step.title}
                  </p>
                  <p className="mt-2 max-w-xl text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
                    {step.detail}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
