import { useId, useState } from "react";
import { buildCollectorFormData, collectorFileError } from "./collectorPackage";
import type { CollectorImportCardProps } from "./types";
import "./forge.css";

/**
 * In-investigation collector import. Collects the package file + explicit
 * consent, then emits onAction("import-collector", formData); the lead wires
 * the POST to .../import-collector and full-replaces via onUpdate.
 * Never executes imported content; validation failures are HTTP 422 with a
 * machine-readable detail list and no partial ingest (contract 1E).
 */
export function CollectorImportCard({
  investigationId,
  onAction,
  onError,
  disabled,
}: CollectorImportCardProps) {
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
    onAction("import-collector", buildCollectorFormData(file));
  };

  return (
    <section
      className="card forge-collector"
      data-testid="forge-collector-import"
      aria-label="Import collector package"
    >
      <div className="card-head">
        <h2>
          <span className="eyebrow">Collector import</span>
        </h2>
        <span className="muted mono" title="Target investigation">
          {investigationId.slice(0, 8)}
        </span>
      </div>
      <p className="muted">
        Import a collector package gathered on the affected computer. Packages are validated
        atomically — any failure rejects the whole import and nothing is executed.
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
          className="button"
          onClick={submit}
          disabled={locked}
        >
          Import package
        </button>
      </div>
    </section>
  );
}
