import { useCallback, useState } from "react";
import {
  fetchInvestigationExport,
  fetchKnowledgeExport,
  investigationExportUrl,
  knowledgeExportUrl,
  type ExportFormat,
} from "../../api";
import { isShellBridgeAvailable, shellSaveFile, ShellBridgeError } from "../shellBridge";
import { formatApiError } from "./formatError";

function exportFilename(id: string, format: ExportFormat): string {
  return `${id}.${format === "json" ? "json" : "md"}`;
}

function exportMime(format: ExportFormat): string {
  return format === "json" ? "application/json" : "text/markdown";
}

async function browserDownload(url: string, filename: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Download failed (HTTP ${res.status}): ${res.statusText}`);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/**
 * Report/knowledge exports. Under the desktop shell the text goes
 * through the native save dialog; in a plain browser it downloads via
 * an anchor. A cancelled or failed shell dialog surfaces honestly and
 * does NOT silently fall back to a second download prompt; only a
 * missing bridge takes the browser path.
 */
export function useExport(): {
  busy: string | null;
  error: string | null;
  investigationUrl: (id: string, format: ExportFormat) => string;
  knowledgeUrl: (entryId: string, format: ExportFormat) => string;
  downloadInvestigation: (id: string, format: ExportFormat) => Promise<void>;
  downloadKnowledge: (entryId: string, format: ExportFormat) => Promise<void>;
  clearError: () => void;
} {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const downloadOne = useCallback(
    async (
      key: string,
      what: string,
      filename: string,
      format: ExportFormat,
      fetchText: () => Promise<string>,
      fallbackUrl: string,
    ) => {
      if (busy) return;
      setBusy(key);
      setError(null);
      try {
        if (isShellBridgeAvailable()) {
          try {
            await shellSaveFile({ filename, text: await fetchText(), mime: exportMime(format) });
            return;
          } catch (e) {
            if (e instanceof ShellBridgeError && e.code === "unavailable") {
              /* bridge vanished mid-call: take the browser path below */
            } else {
              throw e;
            }
          }
        }
        await browserDownload(fallbackUrl, filename);
      } catch (e) {
        if (e instanceof ShellBridgeError) {
          setError(`Export failed: ${e.message}`);
        } else {
          setError(formatApiError(e, what));
        }
      } finally {
        setBusy(null);
      }
    },
    [busy],
  );

  const downloadInvestigation = useCallback(
    (id: string, format: ExportFormat) =>
      downloadOne(
        `investigation-${format}`,
        "Export investigation",
        exportFilename(id, format),
        format,
        () => fetchInvestigationExport(id, format),
        investigationExportUrl(id, format),
      ),
    [downloadOne],
  );

  const downloadKnowledge = useCallback(
    (entryId: string, format: ExportFormat) =>
      downloadOne(
        `knowledge-${format}`,
        "Export knowledge entry",
        exportFilename(entryId, format),
        format,
        () => fetchKnowledgeExport(entryId, format),
        knowledgeExportUrl(entryId, format),
      ),
    [downloadOne],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    busy,
    error,
    investigationUrl: investigationExportUrl,
    knowledgeUrl: knowledgeExportUrl,
    downloadInvestigation,
    downloadKnowledge,
    clearError,
  };
}
