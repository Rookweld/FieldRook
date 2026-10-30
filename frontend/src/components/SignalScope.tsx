import { useId } from "react";

/**
 * SignalScope: FieldRook's diagnostic instrument. A glass scope panel
 * with a drifting waveform, travelling sweep, and readout ticks. The
 * `active` state brightens the instrument while a blocking backend
 * request is in flight — it claims no diagnostic stage or progress,
 * only that the workstation is working.
 */
export function SignalScope({ width = 264, active = false }: { width?: number; active?: boolean }) {
  const height = Math.round((width * 160) / 200);
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const sweepId = `ssg${uid}`;
  const gridId = `sgg${uid}`;
  const clipId = `scc${uid}`;
  return (
    <svg
      className={active ? "scope scope-active" : "scope"}
      width={width}
      height={height}
      viewBox="0 0 200 160"
      role="img"
      aria-label={active ? "Diagnostic instrument: analysis running" : "Diagnostic instrument: standby"}
    >
      <defs>
        <linearGradient id={sweepId} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" style={{ stopColor: "var(--lime)" }} stopOpacity="0" />
          <stop offset="0.5" style={{ stopColor: "var(--lime)" }} stopOpacity="0.35" />
          <stop offset="1" style={{ stopColor: "var(--lime)" }} stopOpacity="0" />
        </linearGradient>
        <pattern id={gridId} width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" style={{ stroke: "var(--lime)" }} strokeOpacity="0.09" strokeWidth="1" />
        </pattern>
        <clipPath id={clipId}>
          <rect x="2" y="10" width="196" height="140" rx="8" />
        </clipPath>
      </defs>
      <rect x="2" y="10" width="196" height="140" rx="8" fillOpacity="0.92" style={{ fill: "var(--sf-deep)", stroke: "var(--line)" }} strokeWidth="1" />
      <rect x="2" y="10" width="196" height="140" rx="8" fill={`url(#${gridId})`} />
      <g clipPath={`url(#${clipId})`}>
      <rect className="scope-sweep" x="0" y="12" width="34" height="136" fill={`url(#${sweepId})`} />
      <path
        className="scope-echo"
        d="M-4,92 C20,92 26,68 44,70 C62,72 58,112 78,110 C98,108 94,78 114,80 C134,82 130,104 150,102 C170,100 174,88 204,90"
        fill="none"
        style={{ stroke: "var(--coral)" }}
        strokeWidth="1.2"
        opacity="0"
      />
      <path
        className="scope-wave"
        d="M-4,84 C20,84 26,60 44,62 C62,64 58,104 78,102 C98,100 94,70 114,72 C134,74 130,96 150,94 C170,92 174,80 204,82"
        fill="none"
        style={{ stroke: "var(--lime)" }}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.85"
      />
      </g>
      <g className="scope-corners" fill="none" style={{ stroke: "var(--muted)" }} strokeWidth="1.4" opacity="0.55">
        <path d="M10,22 V14 H18" />
        <path d="M182,14 H190 V22" />
        <path d="M10,138 V146 H18" />
        <path d="M182,146 H190 V138" />
      </g>
      <g className="scope-ticks" style={{ fill: "var(--sf-track)" }}>
        <rect x="14" y="152" width="10" height="3" className="scope-tick" />
        <rect x="28" y="152" width="16" height="3" className="scope-tick tick-2" />
        <rect x="48" y="152" width="8" height="3" className="scope-tick tick-3" />
        <rect x="60" y="152" width="20" height="3" className="scope-tick tick-4" />
        <rect x="150" y="152" width="12" height="3" className="scope-tick tick-5" />
        <rect x="166" y="152" width="20" height="3" className="scope-tick tick-2" />
      </g>
      <circle className="scope-lamp" cx="184" cy="22" r="2.4" style={{ fill: active ? "var(--coral)" : "var(--sf-track)" }} />
    </svg>
  );
}
