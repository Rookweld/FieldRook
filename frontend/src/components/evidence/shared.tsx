import type { ReactNode } from "react";
import type { SummaryRow } from "../../evidenceSummary";

/** Defensive readers mirroring evidenceSummary semantics. */
export function str(value: unknown): string | null {
  if (typeof value === "string" && value !== "") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

export function obj(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function arr(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function fmt(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    const s = JSON.stringify(value);
    return s.length > 160 ? `${s.slice(0, 157)}…` : s;
  } catch {
    return String(value);
  }
}

/**
 * Service-state dot. Running reads as active (cyan); anything else is
 * neutral information — a stopped service is not an error state.
 */
export function StateDot({ state }: { state: string | null }) {
  const s = (state ?? "").trim().toLowerCase();
  const cls =
    s === "running" || s === "ready" || s === "healthy" || s === "enabled"
      ? "st-dot st-on"
      : s === "stopped" || s === "disabled"
        ? "st-dot st-off"
        : "st-dot st-unknown";
  return (
    <span className={cls} aria-hidden="true" title={state ?? "unknown state"} />
  );
}

export function StatePill({ state }: { state: string | null }) {
  const s = (state ?? "").trim();
  if (!s) return <span className="muted">—</span>;
  const lower = s.toLowerCase();
  const cls =
    lower === "running" || lower === "ready" || lower === "healthy"
      ? "st-pill st-pill-on"
      : lower === "stopped" || lower === "disabled" || lower === "down"
        ? "st-pill st-pill-off"
        : "st-pill";
  return (
    <span className={cls}>
      <StateDot state={s} />
      {s.toUpperCase()}
    </span>
  );
}

export function LevelBadge({ level }: { level: string | null }) {
  const l = (level ?? "").trim();
  if (!l) return null;
  const lower = l.toLowerCase();
  const cls =
    lower.includes("error") || lower.includes("critical") || lower.includes("failure")
      ? "lvl lvl-error"
      : lower.includes("warn")
        ? "lvl lvl-warn"
        : "lvl";
  return <span className={cls}>{l}</span>;
}

/** Compact fact grid used by the generic fallback. */
export function FactGrid({ rows }: { rows: SummaryRow[] }) {
  return (
    <dl className="fact-grid">
      {rows.map((row, i) => (
        <div key={`${row.label}-${i}`} className="fact">
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SliceNote({ shown, total, what }: { shown: number; total: number; what: string }) {
  if (total <= shown) return null;
  return (
    <p className="muted slice-note">
      Showing {shown} of {total} {what} — see Raw JSON for the rest.
    </p>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h4 className="ev-section">{children}</h4>;
}
