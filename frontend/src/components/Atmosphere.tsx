import { useEffect, useRef } from "react";

const EMBERS = [
  { left: "6%", size: 5, delay: "0s", duration: "26s" },
  { left: "14%", size: 3, delay: "7s", duration: "32s" },
  { left: "27%", size: 4, delay: "3s", duration: "29s" },
  { left: "48%", size: 3, delay: "11s", duration: "35s" },
  { left: "63%", size: 5, delay: "5s", duration: "27s" },
  { left: "76%", size: 3, delay: "9s", duration: "31s" },
  { left: "88%", size: 4, delay: "1s", duration: "24s" },
  { left: "94%", size: 3, delay: "14s", duration: "36s" },
];

/**
 * Fixed environmental backdrop: layered gradients, faint technical
 * gridwork, a watermark raven silhouette, drifting embers, and
 * instrument pulses. Pure decoration — pointer-transparent and hidden
 * from assistive tech. All motion freezes under prefers-reduced-motion.
 */
export function Atmosphere() {
  const root = useRef<HTMLDivElement>(null);

  // Whisper-quiet pointer parallax on the background hall only — the
  // reading surface never moves. Skipped for reduced motion, coarse
  // pointers, and narrow viewports.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.innerWidth < 700) return;
    let raf = 0;
    let tx = 0;
    let ty = 0;
    const onMove = (e: PointerEvent) => {
      tx = (e.clientX / window.innerWidth - 0.5) * 2;
      ty = (e.clientY / window.innerHeight - 0.5) * 2;
      if (!raf) {
        raf = requestAnimationFrame(() => {
          raf = 0;
          el.style.setProperty("--px", tx.toFixed(3));
          el.style.setProperty("--py", ty.toFixed(3));
        });
      }
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="atmosphere" aria-hidden="true" ref={root}>
      <div className="atmosphere-hall" />
      <div className="atmosphere-shade" />
      <svg className="atmosphere-grid" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="rook-grid" width="72" height="72" patternUnits="userSpaceOnUse">
            <path d="M 72 0 L 0 0 0 72" fill="none" style={{ stroke: "var(--plum)" }} strokeWidth="1" />
            <circle cx="0" cy="0" r="1.6" style={{ fill: "var(--plum)" }} />
          </pattern>
          <linearGradient id="rook-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" style={{ stopColor: "var(--void)" }} stopOpacity="0" />
            <stop offset="0.55" style={{ stopColor: "var(--void)" }} stopOpacity="0.35" />
            <stop offset="1" style={{ stopColor: "var(--void)" }} stopOpacity="0.92" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1440" height="900" fill="url(#rook-grid)" />
        {/* circuit traces */}
        <g fill="none" style={{ stroke: "var(--line)" }} strokeWidth="1.5" opacity="0.8">
          <path d="M -20 640 H 260 L 320 580 H 560" />
          <path d="M 1460 240 H 1180 L 1120 300 H 940" />
          <path d="M -20 180 H 180 L 240 240" />
        </g>
        <g style={{ fill: "var(--line)" }}>
          <circle className="atmosphere-node" cx="560" cy="580" r="3.5" />
          <circle className="atmosphere-node node-2" cx="940" cy="300" r="3.5" />
          <circle className="atmosphere-node node-3" cx="240" cy="240" r="3.5" />
        </g>
        {/* watermark raven silhouette */}
        <g transform="translate(1050,80) scale(4.4)" style={{ fill: "var(--plum)" }} opacity="0.6">
          <polygon points="34,6 58,14 44,24" />
          <polygon points="40,14 60,26 46,32" />
          <polygon points="22,14 46,16 52,30 40,44 24,42 16,28" />
          <polygon points="16,26 26,24 24,32 8,34" />
          <polygon points="8,34 24,32 22,38 12,38" />
          <polygon points="24,42 40,44 34,58 22,52" />
          <polygon points="34,44 48,38 44,54 34,58" />
        </g>
        <rect x="0" y="0" width="1440" height="900" fill="url(#rook-fade)" />
      </svg>
      <div className="atmosphere-light" />
      <div className="atmosphere-tint" />
      {EMBERS.map((e, i) => (
        <span
          key={i}
          className="ember"
          style={{
            left: e.left,
            width: e.size,
            height: e.size,
            animationDelay: e.delay,
            animationDuration: e.duration,
          }}
        />
      ))}
    </div>
  );
}
