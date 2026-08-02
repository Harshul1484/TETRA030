import { SyllabusUpload } from "@/components/syllabus-upload";
import { SectionTitle } from "@/components/ui";

export const metadata = {
  title: "Analyse a syllabus | Vedha",
};

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

      <section>
        <SectionTitle hint="What happens to the file after it is submitted.">
          What runs
        </SectionTitle>
        <div className="grid gap-5 sm:grid-cols-3">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
            <p className="micro-cap text-[var(--color-ink-mute)]">Extraction</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              Learning outcomes are pulled from the document text, then resolved
              against a taxonomy of 487 skills and 1,646 aliases so that
              &quot;RCC design&quot; and &quot;reinforced concrete&quot; land on
              the same node.
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
            <p className="micro-cap text-[var(--color-ink-mute)]">Comparison</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              Extracted skills are compared against demand from live job
              postings, scored within the course&apos;s own subject area rather
              than the whole market.
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
            <p className="micro-cap text-[var(--color-ink-mute)]">Retention</p>
            <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">
              The uploaded file is parsed in a temporary directory and deleted
              once text extraction finishes. Only the extracted outcomes are
              stored.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
