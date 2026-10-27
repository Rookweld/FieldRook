/**
 * FieldRook diagnostic core: a minimal instrument that breathes while a
 * blocking backend request is in flight. It claims no diagnostic stage —
 * the backend reports none — it only shows the workstation is alive.
 */
export function InvestigationCore({ size = 64 }: { size?: number }) {
  return (
    <svg
      className="diag-core"
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Investigation running"
    >
      <circle cx="32" cy="32" r="29" fill="none" stroke="#26303d" strokeWidth="1.5" />
      <g className="diag-ring-a">
        <circle
          cx="32"
          cy="32"
          r="29"
          fill="none"
          stroke="#6fc3e8"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="40 142"
        />
      </g>
      <g className="diag-ring-b">
        <circle
          cx="32"
          cy="32"
          r="22"
          fill="none"
          stroke="#e2a63d"
          strokeWidth="1.5"
          strokeDasharray="4 10"
        />
      </g>
      <circle
        className="diag-sweep"
        cx="32"
        cy="32"
        r="15"
        fill="none"
        stroke="#6fc3e8"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="24 70"
        opacity="0.7"
      />
      <polygon className="diag-heart" points="32,25 37,32 32,39 27,32" fill="#e2a63d" />
    </svg>
  );
}
