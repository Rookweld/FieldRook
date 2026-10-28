import { useId, useState } from "react";
import { buildCollectorFormData, collectorFileError } from "./collectorPackage";
import type { IntakeCollectorCardProps } from "./types";
import "./forge.css";

/**
 * Pre-investigation collector entry, mounted beside the screenshot input on
 * the intake form. Collects the package file + explicit consent and emits
 * the FormData via onImport; the lead decides ordering (stash-then-start
 * or start-then-import) when wiring .../import-collector.
 */
export function IntakeCollectorCard({ onImport, onError, disabled }: IntakeCollectorCardProps) {
  const fileId = useId();
  const consentId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const locked = disabled === true;

  const submit = () => {
    const fileProblem = collectorFileError(file);
    if (fileProblem) {
      setLocalError(fileProblem);
      onError?.(fileProblem);
      return;
    }
    if (!consent) {
      const msg =
        "Sharing consent is required to import the collector package — check the consent box.";
      setLocalError(msg);
      onError?.(msg);
      return;
    }
    if (!file) return;
    setLocalError(null);
    onImport(buildCollectorFormData(file));
  };

  return (
    <section
      className="card forge-collector"
      data-testid="forge-intake-collector"
      aria-label="Collector package intake"
    >
      <div className="card-head">
        <h2>
          <span className="eyebrow">Have a collector package?</span>
        </h2>
      </div>
      <p className="muted">
        If the collector already ran on the affected computer, attach its .zip package here. It
        joins the investigation as cited evidence once analysis starts.
      </p>
      {localError && (
        <p className="warn" role="alert">
          {localError}
        </p>
      )}
      <div className="file-row">
        <label className="field" htmlFor={fileId}>
          <span>Collector package (.zip)</span>
        </label>
        <input
          id={fileId}
          type="file"
          accept=".zip,application/zip"
          onChange={(e) => setFile(e.currentTarget.files?.[0] ?? null)}
          disabled={locked}
        />
      </div>
      {file && <p className="muted mono">{file.name}</p>}
      <label className="check" htmlFor={consentId}>
        <input
          id={consentId}
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          disabled={locked}
        />
        <span>I am authorized to share this machine&apos;s diagnostics for analysis.</span>
      </label>
      <div className="controls">
        <button
          type="button"
          className="button button-ghost"
          onClick={submit}
          disabled={locked}
        >
          Attach package
        </button>
      </div>
    </section>
  );
}
