type SignalTraceProps = {
  /** Extra class names for placement/sizing. */
  className?: string;
  /**
   * Bounded activity subscription. Pass a monotonic counter the parent
   * bumps on REAL app activity ONLY — navigation, panel expand/collapse,
   * action confirm. Each new value plays one 1.2s highlight sweep over
   * the idle 4.8s ECG loop. Never wire this to timers, keystrokes, or
   * polling; the trace is ornament, never telemetry.
   */
  activityPulse?: number;
  /** Trace colour variant. */
  tone?: "lime" | "coral";
};

/**
 * ECG-style travelling line (4.8s idle loop). ORNAMENTAL: it may react to
 * bounded real app activity via `activityPulse`, but it MUST NEVER be
 * labelled as CPU, network, health, or AI telemetry — no labels, no
 * units, `aria-hidden`.
 */
export function SignalTrace({ className, activityPulse, tone = "lime" }: SignalTraceProps) {
  const cls = ["sf-trace", "sf-motion-decor", className].filter(Boolean).join(" ");
  return (
    <svg
      className={cls}
      viewBox="0 0 260 56"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
      data-tone={tone}
    >
      <line className="sf-trace-grid" x1={0} y1={28} x2={260} y2={28} />
      <path
        className="sf-trace-ghost"
        d="M0 34 L40 34 L52 34 L60 18 L70 44 L78 26 L86 34 L140 34 L152 34 L160 20 L170 42 L178 28 L186 34 L260 34"
      />
      <path
        className="sf-trace-active"
        pathLength={535}
        d="M0 34 L40 34 L52 34 L60 18 L70 44 L78 26 L86 34 L140 34 L152 34 L160 20 L170 42 L178 28 L186 34 L260 34"
      />
      {activityPulse !== undefined && activityPulse > 0 && (
        <path
          key={activityPulse}
          className="sf-trace-pulse"
          pathLength={535}
          d="M0 34 L40 34 L52 34 L60 18 L70 44 L78 26 L86 34 L140 34 L152 34 L160 20 L170 42 L178 28 L186 34 L260 34"
        />
      )}
    </svg>
  );
}
