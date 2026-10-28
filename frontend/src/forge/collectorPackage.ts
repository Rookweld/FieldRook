/**
 * Shared collector-package form helpers (contract forge.collector-manifest/v1,
 * forge.technician-turn/v1 section 1E). The import endpoint is lead-owned;
 * these helpers only validate the picked file and build the FormData the
 * lead POSTs: `file` (ZIP) + `share_consent` ("true" required).
 */

export function collectorFileError(file: File | null): string | null {
  if (!file) return "Choose a collector package (.zip) to import.";
  if (!file.name.toLowerCase().endsWith(".zip")) {
    return "Collector packages are ZIP files — choose a .zip file.";
  }
  return null;
}

export function buildCollectorFormData(file: File): FormData {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("share_consent", "true");
  return form;
}
