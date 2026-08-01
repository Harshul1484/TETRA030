/**
 * Components follow frontend/DESIGN.md: a monochrome editorial frame with
 * oversized pastel colour blocks carrying the content. Shadows and gradients
 * are deliberately absent; colour and type do the work.
 */

import { categoryBlock } from "@/lib/theme";

export function Card({
  children,
  className = "",
  block,
}: {
  children: React.ReactNode;
  className?: string;
  /** A pastel block colour, or omitted for the plain white surface. */
  block?: string;
}) {
  if (block) {
    return (
      <div
        className={`rounded-[var(--radius-lg)] border border-[var(--color-hairline)] p-8 ${className}`}
        style={{ backgroundColor: block }}
      >
        {children}
      </div>
    );
  }

  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-8 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="mb-6">
      <h2 className="display-md text-[var(--color-ink)]">{children}</h2>
      {hint ? (
        <p className="mt-2 max-w-2xl text-[16px] text-[var(--color-ink-soft)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function scoreTone(score: number | null): string {
  if (score === null) return "text-[var(--color-ink-mute)]";
  if (score >= 60) return "text-[var(--color-success)]";
  if (score >= 30) return "text-[var(--color-severity-high)]";
  return "text-[var(--color-severity-critical)]";
}

export function HealthScore({
  score,
  size = "large",
}: {
  score: number | null;
  size?: "large" | "small";
}) {
  const display = score === null ? "n/a" : score.toFixed(1);
  const tone = scoreTone(score);

  if (size === "small") {
    return (
      <span className={`tabular text-[24px] font-medium ${tone}`}>
        {display}
      </span>
    );
  }

  return (
    <div className="flex items-baseline gap-2">
      <span className={`tabular display-xl ${tone}`}>{display}</span>
      <span className="text-[16px] text-[var(--color-ink-mute)]">/ 100</span>
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tones: Record<string, string> = {
    critical: "bg-[var(--color-severity-critical)] text-white",
    high: "bg-[var(--color-severity-high)] text-white",
    moderate: "bg-[var(--color-severity-moderate)] text-white",
    low: "bg-[var(--color-hairline)] text-[var(--color-ink-soft)]",
  };

  return (
    <span
      className={`micro-cap inline-flex shrink-0 rounded-[var(--radius-xs)] px-2 py-1 ${
        tones[severity] ?? tones.low
      }`}
    >
      {severity}
    </span>
  );
}

/** Category tags use the same pastel a node uses in the graph. */
export function CategoryTag({ category }: { category: string }) {
  const block = categoryBlock(category);
  return (
    <span className="micro-cap inline-flex shrink-0 items-center gap-1.5 text-[var(--color-ink-mute)]">
      <span
        aria-hidden
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: block.dot }}
      />
      {block.label}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div>
      <p className="micro-cap text-[var(--color-ink-mute)]">{label}</p>
      <p className="tabular mt-2 text-[40px] font-light leading-none text-[var(--color-ink)]">
        {value}
      </p>
      {hint ? (
        <p className="caption mt-2 text-[var(--color-ink-mute)]">{hint}</p>
      ) : null}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "quiet";
  type?: "button" | "submit";
}) {
  const variants = {
    primary: "bg-[var(--color-ink)] text-white hover:bg-[var(--color-ink-soft)]",
    secondary:
      "bg-[var(--color-surface)] text-[var(--color-ink)] border border-[var(--color-ink)] hover:bg-[var(--color-surface-soft)]",
    quiet:
      "bg-transparent text-[var(--color-ink-mute)] hover:text-[var(--color-ink)]",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-[44px] items-center justify-center rounded-[var(--radius-full)] px-6 py-2.5 text-[16px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]}`}
    >
      {children}
    </button>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <Card block="var(--color-block-orchid)">
      <p className="card-title text-[var(--color-ink)]">Could not load data</p>
      <p className="mt-3 text-[16px] text-[var(--color-ink-soft)]">{message}</p>
      <p className="caption mt-5 text-[var(--color-ink-soft)]">
        The API may not be running. Start it with{" "}
        <code className="rounded-[var(--radius-xs)] bg-[var(--color-surface)]/70 px-1.5 py-0.5 font-mono">
          docker compose up -d
        </code>{" "}
        then seed it with{" "}
        <code className="rounded-[var(--radius-xs)] bg-[var(--color-surface)]/70 px-1.5 py-0.5 font-mono">
          docker compose exec backend python -m app.seed
        </code>
      </p>
    </Card>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <Card block="var(--color-surface-soft)" className="text-center">
      <p className="card-title text-[var(--color-ink)]">{title}</p>
      <p className="mx-auto mt-3 max-w-md text-[16px] text-[var(--color-ink-soft)]">
        {body}
      </p>
    </Card>
  );
}

export function DemandBar({ value, tone }: { value: number; tone?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-[var(--radius-full)] bg-[var(--color-hairline)]">
      <div
        className="h-full rounded-[var(--radius-full)]"
        style={{
          width: `${Math.min(100, Math.max(4, value * 100))}%`,
          backgroundColor: tone ?? "var(--color-ink)",
        }}
      />
    </div>
  );
}
