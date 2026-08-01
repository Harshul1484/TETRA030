import { healthTone } from "@/lib/api";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-slate-900/40 p-5 ${className}`}
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
    <div className="mb-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        {children}
      </h2>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

/** The headline number. Scale it up; it is the thing a dean reacts to. */
export function HealthScore({
  score,
  size = "large",
}: {
  score: number | null;
  size?: "large" | "small";
}) {
  const tone = healthTone(score);
  const display = score === null ? "n/a" : score.toFixed(1);

  if (size === "small") {
    return <span className={`font-mono text-lg font-semibold ${tone}`}>{display}</span>;
  }

  return (
    <div className="flex items-baseline gap-2">
      <span className={`font-mono text-5xl font-bold tabular-nums ${tone}`}>
        {display}
      </span>
      <span className="text-sm text-slate-500">/ 100</span>
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tones: Record<string, string> = {
    critical: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    high: "border-orange-500/40 bg-orange-500/10 text-orange-300",
    moderate: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    low: "border-slate-600/40 bg-slate-600/10 text-slate-400",
  };
  return (
    <span
      className={`inline-flex shrink-0 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        tones[severity] ?? tones.low
      }`}
    >
      {severity}
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
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-slate-100">
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <Card className="border-rose-500/30 bg-rose-500/5">
      <p className="text-sm font-medium text-rose-300">Could not load data</p>
      <p className="mt-1 text-sm text-slate-400">{message}</p>
      <p className="mt-3 text-xs text-slate-500">
        The API may not be running. Start it with{" "}
        <code className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-slate-300">
          docker compose up -d
        </code>{" "}
        and seed it with{" "}
        <code className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-slate-300">
          docker compose exec backend python -m app.seed
        </code>
      </p>
    </Card>
  );
}

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <Card className="text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{body}</p>
    </Card>
  );
}

/** A horizontal proportion bar. Used for market demand, which is a share. */
export function DemandBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
      <div
        className="h-full rounded-full bg-sky-500/70"
        style={{ width: `${Math.min(100, Math.max(2, value * 100))}%` }}
      />
    </div>
  );
}
