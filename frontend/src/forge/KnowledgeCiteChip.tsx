import type { KnowledgeCiteChipProps } from "./types";
import "./forge.css";

/**
 * Reference citation rendered beside evidence chips. Props-fed and read-only:
 * no fetching (the lead adds fetchReferencePassages). When a passage is
 * supplied, its span renders as a quoted technician-visible excerpt —
 * reference text is never a system instruction (contract 1D).
 */
export function KnowledgeCiteChip({ citation, passage, onSelect }: KnowledgeCiteChipProps) {
  const label = `Reference: ${citation.title} (${citation.locator})`;
  const chip = onSelect ? (
    <button
      type="button"
      className="chip chip-button forge-cite"
      onClick={() => onSelect(citation)}
      title={citation.locator}
      aria-label={label}
      data-testid={`forge-cite-${citation.doc_id}`}
    >
      <span className="forge-cite-tag" aria-hidden="true">
        REF
      </span>{" "}
      {citation.title}
    </button>
  ) : (
    <code
      className="chip forge-cite"
      title={citation.locator}
      data-testid={`forge-cite-${citation.doc_id}`}
    >
      <span className="forge-cite-tag" aria-hidden="true">
        REF
      </span>{" "}
      {citation.title}
    </code>
  );

  if (!passage) return chip;
  return (
    <span className="forge-cite-wrap">
      {chip}
      <details className="forge-cite-details">
        <summary>Quoted excerpt</summary>
        <blockquote className="quote">
          <p>{passage.span}</p>
          <footer className="muted">
            {passage.title} · {passage.path}
            {passage.anchor ? `#${passage.anchor}` : ""}
          </footer>
        </blockquote>
      </details>
    </span>
  );
}
