type CircuitVeinsProps = {
  /** Extra class names for placement (positioning is the parent's job). */
  className?: string;
  /** Accessible label when the veins carry meaning; default hides them. */
  ariaLabel?: string;
};

/**
 * Low-priority atmospheric circuit pulses (SVG stroke-dashoffset, 13s and
 * 18s loops, glowing nodes). Pure ornament: `aria-hidden` unless the
 * caller passes `ariaLabel`.
 *
 * Placement rule (M026 §4): NEVER behind reading panels. Put CircuitVeins
 * in hero/launchpad chrome only; as a backstop, `.sf-reading` containers
 * hide all `.sf-motion-decor` via CSS.
 */
export function CircuitVeins({ className, ariaLabel }: CircuitVeinsProps) {
  const cls = className ? `sf-circuit sf-motion-decor ${className}` : "sf-circuit sf-motion-decor";
  const hidden = ariaLabel === undefined;
  return (
    <svg
      className={cls}
      viewBox="0 0 800 400"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden={hidden}
      role={hidden ? undefined : "img"}
      aria-label={ariaLabel}
      focusable="false"
    >
      <path className="sf-vein-base" d="M-20 330 C 140 300, 220 180, 380 200 S 640 320, 820 140" />
      <path className="sf-vein-base" d="M-20 90 C 160 120, 300 40, 470 90 S 660 200, 820 90" />
      <path
        className="sf-vein-lit"
        pathLength={704}
        d="M-20 330 C 140 300, 220 180, 380 200 S 640 320, 820 140"
      />
      <path
        className="sf-vein-lit sf-alt"
        pathLength={704}
        d="M-20 90 C 160 120, 300 40, 470 90 S 660 200, 820 90"
      />
      <circle className="sf-vein-node" cx={380} cy={200} r={3} />
      <circle className="sf-vein-node sf-alt" cx={470} cy={90} r={3} />
      <circle className="sf-vein-node sf-alt" cx={640} cy={260} r={2.5} />
    </svg>
  );
}
