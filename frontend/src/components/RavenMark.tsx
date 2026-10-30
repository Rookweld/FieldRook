/**
 * Original ROOKWELD raven mark: an angular geometric raven head drawn
 * from layered polygons. Duotone via currentColor + forge gold eye.
 */
export function RavenMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Rookweld raven mark"
    >
      {/* rear crest feathers */}
      <polygon points="34,6 58,14 44,24" fill="currentColor" opacity="0.45" />
      <polygon points="40,14 60,26 46,32" fill="currentColor" opacity="0.6" />
      {/* crown + head */}
      <polygon points="22,14 46,16 52,30 40,44 24,42 16,28" fill="currentColor" />
      {/* beak */}
      <polygon points="16,26 26,24 24,32 8,34" fill="currentColor" opacity="0.85" />
      <polygon points="8,34 24,32 22,38 12,38" fill="currentColor" opacity="0.6" />
      {/* neck plumage */}
      <polygon points="24,42 40,44 34,58 22,52" fill="currentColor" opacity="0.7" />
      <polygon points="34,44 48,38 44,54 34,58" fill="currentColor" opacity="0.5" />
      {/* forge-gold eye */}
      <polygon points="33,27 39,27 37,32" style={{ fill: "var(--coral)" }} />
    </svg>
  );
}
