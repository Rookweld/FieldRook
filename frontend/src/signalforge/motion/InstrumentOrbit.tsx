type InstrumentOrbitProps = {
  /** Extra class names for placement/sizing. */
  className?: string;
  /** Diameter in px. Defaults to 220. */
  size?: number;
  /** Ring rotation period in seconds (20–70s instrument range). */
  ringPeriodSec?: number;
  /** Scan arc period in seconds (20–70s instrument range). */
  scanPeriodSec?: number;
  /** Accessible label when the orbit carries meaning; default hides it. */
  ariaLabel?: string;
};

function clampPeriod(sec: number): number {
  if (!Number.isFinite(sec)) return 20;
  return Math.min(70, Math.max(20, sec));
}

/**
 * Soft instrument identity: a hairline dashed ring (default 70s) plus a
 * scan arc (default 20s), rotation via composited transforms only.
 * Pure ornament: `aria-hidden` unless the caller passes `ariaLabel`.
 */
export function InstrumentOrbit({
  className,
  size = 220,
  ringPeriodSec = 70,
  scanPeriodSec = 20,
  ariaLabel,
}: InstrumentOrbitProps) {
  const cls = className ? `sf-orbit sf-motion-decor ${className}` : "sf-orbit sf-motion-decor";
  const hidden = ariaLabel === undefined;
  return (
    <div
      className={cls}
      style={{ width: size, height: size }}
      aria-hidden={hidden}
      role={hidden ? undefined : "img"}
      aria-label={ariaLabel}
    >
      <span className="sf-orbit-ring" style={{ animationDuration: `${clampPeriod(ringPeriodSec)}s` }} />
      <span className="sf-orbit-scan" style={{ animationDuration: `${clampPeriod(scanPeriodSec)}s` }} />
      <span className="sf-orbit-core" />
    </div>
  );
}
