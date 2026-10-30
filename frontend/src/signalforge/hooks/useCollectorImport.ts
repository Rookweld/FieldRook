import { useCallback, useRef, useState } from "react";
import { uploadCollectorPackage } from "../../api";
import { buildCollectorFormData, collectorFileError } from "../../forge/collectorPackage";
import type { InvestigationResponse } from "../../types";
import { type ShellOpenFileResult } from "../shellBridge";
import { formatApiError } from "./formatError";

export interface CollectorImportBinding {
  investigationId: string | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

function base64ToFile(base64: string, name: string): File {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new File([bytes.buffer], name, { type: "application/zip" });
}

/**
 * Collector package import. Accepts a File (picker or window drop) or a
 * shell openFile result (native dialog). Validation failures are honest:
 * the backend rejects atomically (HTTP 422/409/413) with no partial
 * ingest, and the message is surfaced verbatim.
 */
export function useCollectorImport(binding: CollectorImportBinding): {
  busy: boolean;
  error: string | null;
  importFile: (file: File | null, consent: boolean) => Promise<void>;
  importShellFile: (result: ShellOpenFileResult, consent: boolean) => Promise<void>;
  clearError: () => void;
} {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const report = useCallback((message: string) => {
    setError(message);
    bindingRef.current.onError?.(message);
  }, []);

  const upload = useCallback(
    async (file: File) => {
      const { investigationId, onUpdate, disabled } = bindingRef.current;
      if (disabled || busy) return;
      if (!investigationId) {
        report("No investigation is open.");
        return;
      }
      setBusy(true);
      setError(null);
      try {
        onUpdate(await uploadCollectorPackage(investigationId, buildCollectorFormData(file)));
      } catch (e) {
        report(formatApiError(e, "Collector import"));
      } finally {
        setBusy(false);
      }
    },
    [busy, report],
  );

  const importFile = useCallback(
    async (file: File | null, consent: boolean) => {
      const fileProblem = collectorFileError(file);
      if (fileProblem) {
        report(fileProblem);
        return;
      }
      if (!consent) {
        report("Sharing consent is required to import the collector package — check the consent box.");
        return;
      }
      if (!file) return;
      await upload(file);
    },
    [report, upload],
  );

  const importShellFile = useCallback(
    async (result: ShellOpenFileResult, consent: boolean) => {
      if (!consent) {
        report("Sharing consent is required to import the collector package — check the consent box.");
        return;
      }
      if (result.contentBase64 === null) {
        report(
          `The shell returned the path ${result.path} without file bytes, so the browser cannot read the package. ` +
            "Pick the .zip through the file picker instead.",
        );
        return;
      }
      await upload(base64ToFile(result.contentBase64, result.name));
    },
    [report, upload],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { busy, error, importFile, importShellFile, clearError };
}
