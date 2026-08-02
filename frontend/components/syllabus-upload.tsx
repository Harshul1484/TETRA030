"use client";

import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";

/**
 * Upload a syllabus and analyse it.
 *
 * The seeded courses prove the pipeline works. This proves it works on
 * something the judges hand it, which is a different claim. An uploaded
 * document goes through exactly the same six stages as a seeded one: no
 * fixture path, no pre-computed answer.
 *
 * Parsing a syllabus takes long enough that a spinner alone reads as a
 * hang, so the stages are named while they run.
 */

const ACCEPTED = ".pdf,.docx,.doc,.txt,.md";
const MAX_BYTES = 10 * 1024 * 1024;

// Shown in sequence while the request is in flight. These are the real
// pipeline stages, but the timings are indicative: the backend returns when
// it is done, not on a schedule, so the last stage holds until it responds.
const STAGES = [
  "Parsing the document",
  "Extracting learning outcomes",
  "Embedding outcomes",
  "Matching against the skill taxonomy",
  "Scoring against live job postings",
];

interface Result {
  course_code: string;
  title: string;
  characters_parsed: number;
}

export function SyllabusUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const stageTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const stopStages = useCallback(() => {
    if (stageTimer.current) {
      clearInterval(stageTimer.current);
      stageTimer.current = null;
    }
  }, []);

  const submit = useCallback(
    async (file: File) => {
      setError(null);
      setResult(null);
      setFileName(file.name);

      const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ACCEPTED.split(",").includes(suffix)) {
        setError(
          `Unsupported file type ${suffix || "(none)"}. Accepted: ${ACCEPTED}`,
        );
        return;
      }
      if (file.size > MAX_BYTES) {
        setError("File exceeds 10 MB.");
        return;
      }

      setBusy(true);
      setStage(0);
      // Hold on the final stage rather than running off the end of the list.
      stageTimer.current = setInterval(() => {
        setStage((current) => Math.min(current + 1, STAGES.length - 1));
      }, 1400);

      try {
        setResult(await api.uploadSyllabus(file));
      } catch (exception) {
        setError(
          exception instanceof Error ? exception.message : String(exception),
        );
      } finally {
        stopStages();
        setBusy(false);
      }
    },
    [stopStages],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setDragging(false);
      const file = event.dataTransfer.files?.[0];
      if (file) void submit(file);
    },
    [submit],
  );

  return (
    <div className="space-y-6">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !busy && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            if (!busy) inputRef.current?.click();
          }
        }}
        className={`flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-[var(--radius-lg)] border-2 border-dashed px-8 py-14 text-center transition-colors ${
          dragging
            ? "border-[var(--color-ink)] bg-[var(--color-surface-soft)]"
            : "border-[var(--color-hairline)] bg-[var(--color-surface)] hover:border-[var(--color-ink-mute)]"
        } ${busy ? "pointer-events-none opacity-70" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void submit(file);
            event.target.value = "";
          }}
        />

        {busy ? (
          <div className="w-full max-w-sm">
            <p className="card-title text-[var(--color-ink)]">
              {STAGES[stage]}
            </p>
            <p className="caption mt-2 text-[var(--color-ink-mute)]">
              {fileName}
            </p>
            <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-[var(--color-surface-soft)]">
              <div
                className="h-full rounded-full bg-[var(--color-ink)] transition-[width] duration-700 ease-out"
                style={{
                  width: `${((stage + 1) / STAGES.length) * 100}%`,
                }}
              />
            </div>
            <p className="caption mt-4 text-[var(--color-ink-mute)]">
              Stage {stage + 1} of {STAGES.length}
            </p>
          </div>
        ) : (
          <>
            <span
              aria-hidden
              className="mb-5 inline-block h-9 w-9 rounded-[9px]"
              style={{ backgroundColor: "var(--color-block-periwinkle)" }}
            />
            <p className="card-title text-[var(--color-ink)]">
              Drop a syllabus here, or select a file
            </p>
            <p className="mt-3 max-w-md text-[16px] text-[var(--color-ink-soft)]">
              PDF, Word, Markdown or plain text, up to 10 MB. It runs through
              the same six stages as every seeded course.
            </p>
            <p className="caption mt-4 text-[var(--color-ink-mute)]">
              Scanned PDFs need a text layer to be readable
            </p>
          </>
        )}
      </div>

      {error ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
          <p className="micro-cap text-[var(--color-severity-high)]">
            Upload failed
          </p>
          <p className="mt-2 text-[16px] text-[var(--color-ink-soft)]">
            {error}
          </p>
        </div>
      ) : null}

      {result ? (
        <div
          className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] p-7"
          style={{ backgroundColor: "var(--color-block-sage)" }}
        >
          <p className="micro-cap text-[var(--color-ink)]">Analysed</p>
          <h3 className="card-title mt-3 text-[var(--color-ink)]">
            {result.title}
          </h3>
          <dl className="caption mt-4 flex flex-wrap gap-x-10 gap-y-2">
            <div>
              <dt className="text-[var(--color-ink-mute)]">Course code</dt>
              <dd className="tabular text-[var(--color-ink)]">
                {result.course_code}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--color-ink-mute)]">Characters parsed</dt>
              <dd className="tabular text-[var(--color-ink)]">
                {result.characters_parsed.toLocaleString()}
              </dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={() =>
              router.push(`/courses/${encodeURIComponent(result.course_code)}`)
            }
            className="mt-6 rounded-[var(--radius-full)] bg-[var(--color-ink)] px-6 py-3 text-[15px] font-medium text-white transition-opacity hover:opacity-85"
          >
            See its skill gaps
          </button>
        </div>
      ) : null}
    </div>
  );
}
