import type {
  CollectorPackageRecord,
  Contradiction,
  EvidenceItem,
  EvidenceRefresh,
  InvestigationResponse,
} from "./types";

/**
 * Evidence Lens (M028.B): deterministic, read-only helpers over persisted
 * investigation data. Every conclusion here is grounded in fields the
 * backend already stores — evidence records, refresh_of/refreshes linkage,
 * collector package records, and cited contradiction ids.
 *
 * Comparison semantics mirror backend/app/analysis/refresh.py exactly
 * (volatile keys, list cap, value cap), plus the collector-envelope strip
 * from backend/app/routers/collector_import.py. Imported archive contents
 * are treated as data throughout: keys and values are rendered, capped,
 * and redacted — never interpreted.
 */

export const LENS_MAX_FIELDS = 200;
export const LENS_MAX_VALUE_CHARS = 160;
export const LENS_MAX_LIST_ITEMS = 25;
export const LENS_MAX_DEPTH = 12;
export const LENS_MAX_CHANGE_ROWS = 10;

const VOLATILE_KEYS: ReadonlySet<string> = new Set([
  "summary",
  "warnings",
  "query_ms",
  "heartbeat_age_s",
  "uptime_s",
  "memory_mb",
  "collected_at",
  "timestamp",
  "started",
]);

const SENSITIVE_KEY =
  /password|passwd|secret|token|api[-_]?key|private[-_]?key|credential|ssn|credit[-_]?card|authorization/i;

const REDACTED = "[redacted]";

export type LensRecordStatus = "error" | "imported" | "live" | "fixture" | "unknown";

export type LensHost =
  | { kind: "collector"; packageId: string; hostHash: string | null }
  | { kind: "local" }
  | { kind: "fixture" }
  | { kind: "unknown" };

export type LensFieldState = "changed" | "unchanged" | "unknown";

export type LensFieldRow = {
  path: string;
  before: string | null;
  after: string | null;
  state: LensFieldState;
};

export type LensFieldDiff = {
  rows: LensFieldRow[];
  changed: number;
  unchanged: number;
  unknown: number;
  truncated: boolean;
};

export type LensPairResolution = "ok" | "failed-new" | "missing-old" | "missing-new";

export type LensPair = {
  refresh: EvidenceRefresh;
  oldItem: EvidenceItem | null;
  newItem: EvidenceItem | null;
  resolution: LensPairResolution;
  /** The new item's refresh_of points back at the old item. Null when unknown. */
  refreshOfAgrees: boolean | null;
  diff: LensFieldDiff;
};

export type LensSnapshot =
  | { state: "no-packages" }
  | { state: "single-snapshot"; package: CollectorPackageRecord; total: number }
  | {
      state: "host-mismatch";
      packageA: CollectorPackageRecord;
      packageB: CollectorPackageRecord;
      total: number;
    }
  | {
      state: "insufficient-evidence";
      packageA: CollectorPackageRecord;
      packageB: CollectorPackageRecord;
      total: number;
    }
  | {
      state: "compared";
      packageA: CollectorPackageRecord;
      packageB: CollectorPackageRecord;
      hostHash: string;
      pairs: LensPair[];
      total: number;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isEvidenceItem(value: unknown): value is EvidenceItem {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.category === "string" &&
    typeof value.source === "string" &&
    typeof value.collected_at === "string"
  );
}

function compareText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Deterministic record order: collection time, then record id. Raw string
 * comparison keeps malformed timestamps reproducible instead of random.
 */
export function sortEvidenceRecords(
  evidence: readonly EvidenceItem[] | null | undefined,
): EvidenceItem[] {
  if (!Array.isArray(evidence)) return [];
  return evidence
    .filter(isEvidenceItem)
    .slice()
    .sort(
      (a, b) =>
        compareText(a.collected_at, b.collected_at) || compareText(a.id, b.id),
    );
}

export function recordStatus(item: EvidenceItem): LensRecordStatus {
  if (item.error !== null && item.error !== undefined) return "error";
  const source = typeof item.source === "string" ? item.source : "";
  if (source.startsWith("collector:")) return "imported";
  if (source.includes(":live")) return "live";
  if (source.includes("fixture")) return "fixture";
  return "unknown";
}

/** Short, non-identifying host label: a hash prefix, never a hostname. */
export function shortHostHash(hash: string | null | undefined): string {
  if (typeof hash !== "string" || hash === "") return "unverified host";
  return `host ${hash.slice(0, 12)}…`;
}

function collectorPackageId(item: EvidenceItem): string | null {
  const source = typeof item.source === "string" ? item.source : "";
  if (source.startsWith("collector:")) {
    const parts = source.split(":");
    if (parts.length > 1 && parts[1] !== "") return parts[1];
  }
  if (isRecord(item.data) && isRecord(item.data.provenance)) {
    const collector = item.data.provenance.collector;
    if (isRecord(collector) && typeof collector.package_id === "string") {
      return collector.package_id;
    }
  }
  return null;
}

/**
 * Grounded host identity for one record. Collector records resolve through
 * the validated package list; live tool readings on a local-target case
 * describe this host; fixtures describe no machine at all.
 */
export function recordHost(item: EvidenceItem, inv: InvestigationResponse): LensHost {
  const packageId = collectorPackageId(item);
  if (packageId !== null) {
    const packages = Array.isArray(inv.collector_packages) ? inv.collector_packages : [];
    const match = packages.find((p) => isRecord(p) && p.package_id === packageId);
    const hash =
      match !== undefined && typeof match.hostname_hash === "string" && match.hostname_hash !== ""
        ? match.hostname_hash
        : null;
    return { kind: "collector", packageId, hostHash: hash };
  }
  const source = typeof item.source === "string" ? item.source : "";
  if (source.startsWith("tool:") && source.endsWith(":live") && inv.target === "local") {
    return { kind: "local" };
  }
  if (source.includes("fixture")) return { kind: "fixture" };
  return { kind: "unknown" };
}

export function hostLabel(host: LensHost): string {
  switch (host.kind) {
    case "collector":
      return `${shortHostHash(host.hostHash)} · package ${host.packageId}`;
    case "local":
      return "this host (local case, live reading)";
    case "fixture":
      return "fixture (no machine)";
    case "unknown":
      return "unknown origin";
  }
}

/**
 * Copy evidence data minus the volatile import envelope, mirroring the
 * backend's comparable-data strip: package_id/import stamps differ on
 * every import by construction and must never count as a change.
 */
export function comparableData(data: unknown): Record<string, unknown> {
  if (!isRecord(data)) return {};
  const copy: Record<string, unknown> = { ...data };
  if (isRecord(copy.provenance)) {
    const provenance: Record<string, unknown> = { ...copy.provenance };
    delete provenance.collector;
    copy.provenance = provenance;
  }
  return copy;
}

function renderScalar(value: unknown): string {
  if (typeof value === "string") {
    const text = JSON.stringify(value) ?? `"${value}"`;
    return text.length <= LENS_MAX_VALUE_CHARS ? text : `${text.slice(0, LENS_MAX_VALUE_CHARS - 3)}...`;
  }
  let text: string;
  try {
    text = JSON.stringify(value) ?? String(value);
  } catch {
    text = String(value);
  }
  return text.length <= LENS_MAX_VALUE_CHARS ? text : `${text.slice(0, LENS_MAX_VALUE_CHARS - 3)}...`;
}

type FlattenState = {
  out: Map<string, string>;
  total: number;
};

function flattenLensValue(
  value: unknown,
  prefix: string,
  depth: number,
  state: FlattenState,
): void {
  const label = prefix === "" ? "(record)" : prefix;
  if (depth > LENS_MAX_DEPTH) {
    state.out.set(label, "[nested too deep]");
    state.total += 1;
    return;
  }
  if (isRecord(value)) {
    const keys = Object.keys(value)
      .filter((key) => !VOLATILE_KEYS.has(key))
      .sort();
    if (keys.length === 0) {
      state.out.set(label, "{}");
      state.total += 1;
      return;
    }
    for (const key of keys) {
      if (state.total >= LENS_MAX_FIELDS) return;
      const path = prefix === "" ? key : `${prefix}.${key}`;
      const child = value[key];
      if (SENSITIVE_KEY.test(key) && (typeof child === "string" || typeof child === "number")) {
        state.out.set(path, REDACTED);
        state.total += 1;
        continue;
      }
      flattenLensValue(child, path, depth + 1, state);
    }
    return;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      state.out.set(label, "[]");
      state.total += 1;
      return;
    }
    if (value.length > LENS_MAX_LIST_ITEMS) {
      state.out.set(label, `[list of ${value.length}]`);
      state.total += 1;
      return;
    }
    for (let index = 0; index < value.length; index += 1) {
      if (state.total >= LENS_MAX_FIELDS) return;
      flattenLensValue(value[index], `${label}[${index}]`, depth + 1, state);
    }
    return;
  }
  state.out.set(label, renderScalar(value));
  state.total += 1;
}

function flattenForLens(data: unknown): { fields: Map<string, string>; truncated: boolean } {
  const state: FlattenState = { out: new Map(), total: 0 };
  flattenLensValue(comparableData(data), "", 0, state);
  return { fields: state.out, truncated: state.total >= LENS_MAX_FIELDS };
}

/**
 * Truthful measured-field diff between two readings. Volatile and
 * envelope fields are excluded exactly like the backend verdict; the
 * verdict itself always comes from the stored refresh record, never
 * from this presentational diff.
 */
export function diffMeasuredFields(
  oldData: unknown,
  newData: unknown,
): LensFieldDiff {
  const oldFlat = flattenForLens(oldData);
  const newFlat = flattenForLens(newData);
  const paths = [...new Set([...oldFlat.fields.keys(), ...newFlat.fields.keys()])].sort();
  const rows: LensFieldRow[] = [];
  let changed = 0;
  let unchanged = 0;
  const malformedOld = !isRecord(oldData);
  const malformedNew = !isRecord(newData);
  for (const path of paths) {
    const before = oldFlat.fields.get(path) ?? null;
    const after = newFlat.fields.get(path) ?? null;
    if (before === after) {
      unchanged += 1;
      rows.push({ path, before, after, state: "unchanged" });
    } else {
      changed += 1;
      rows.push({ path, before, after, state: "changed" });
    }
  }
  const unknown = malformedOld || malformedNew ? 1 : 0;
  const ordered = rows.sort(
    (a, b) =>
      (a.state === "changed" ? 0 : 1) - (b.state === "changed" ? 0 : 1) ||
      compareText(a.path, b.path),
  );
  return {
    rows: ordered,
    changed,
    unchanged,
    unknown,
    truncated: oldFlat.truncated || newFlat.truncated,
  };
}

function emptyDiff(): LensFieldDiff {
  return { rows: [], changed: 0, unchanged: 0, unknown: 0, truncated: false };
}

function unknownDiff(note: string): LensFieldDiff {
  return {
    rows: [{ path: "(record)", before: null, after: note, state: "unknown" }],
    changed: 0,
    unchanged: 0,
    unknown: 1,
    truncated: false,
  };
}

function isRefresh(value: unknown): value is EvidenceRefresh {
  return (
    isRecord(value) &&
    typeof value.old_evidence_id === "string" &&
    typeof value.tool_name === "string" &&
    typeof value.compared_at === "string"
  );
}

export function sortRefreshes(
  refreshes: readonly EvidenceRefresh[] | null | undefined,
): EvidenceRefresh[] {
  if (!Array.isArray(refreshes)) return [];
  return refreshes
    .filter(isRefresh)
    .slice()
    .sort(
      (a, b) =>
        compareText(a.compared_at, b.compared_at) ||
        compareText(a.old_evidence_id, b.old_evidence_id),
    );
}

function buildPair(
  refresh: EvidenceRefresh,
  byId: ReadonlyMap<string, EvidenceItem>,
): LensPair {
  const oldItem = byId.get(refresh.old_evidence_id) ?? null;
  const newItem =
    typeof refresh.new_evidence_id === "string"
      ? (byId.get(refresh.new_evidence_id) ?? null)
      : null;
  if (oldItem === null) {
    return {
      refresh,
      oldItem,
      newItem,
      resolution: "missing-old",
      refreshOfAgrees: null,
      diff: unknownDiff("historical record is not on this case"),
    };
  }
  if (typeof refresh.new_evidence_id === "string" && newItem === null) {
    return {
      refresh,
      oldItem,
      newItem,
      resolution: "missing-new",
      refreshOfAgrees: null,
      diff: unknownDiff("current record is not on this case"),
    };
  }
  if (newItem === null || newItem.error !== null) {
    return {
      refresh,
      oldItem,
      newItem,
      resolution: "failed-new",
      refreshOfAgrees: newItem === null ? null : newItem.refresh_of === oldItem.id,
      diff: emptyDiff(),
    };
  }
  if (oldItem.error !== null && newItem.error === null) {
    return {
      refresh,
      oldItem,
      newItem,
      resolution: "ok",
      refreshOfAgrees: newItem.refresh_of === oldItem.id,
      diff: {
        rows: [
          {
            path: "(collection)",
            before: `error: ${oldItem.error}`,
            after: "collected",
            state: "changed",
          },
        ],
        changed: 1,
        unchanged: 0,
        unknown: 0,
        truncated: false,
      },
    };
  }
  return {
    refresh,
    oldItem,
    newItem,
    resolution: "ok",
    refreshOfAgrees: newItem.refresh_of === oldItem.id,
    diff: diffMeasuredFields(oldItem.data, newItem.data),
  };
}

/**
 * Original-vs-reverify pairs from real refresh records. No record, no
 * pair: refresh_of pointers without a stored comparison are never
 * turned into invented verdicts.
 */
export function buildRefreshPairs(inv: InvestigationResponse): LensPair[] {
  const byId = new Map<string, EvidenceItem>();
  if (Array.isArray(inv.evidence)) {
    for (const item of inv.evidence) {
      if (isEvidenceItem(item)) byId.set(item.id, item);
    }
  }
  return sortRefreshes(inv.refreshes).map((refresh) => buildPair(refresh, byId));
}

function isPackage(value: unknown): value is CollectorPackageRecord {
  return isRecord(value) && typeof value.package_id === "string";
}

export function sortPackages(
  packages: readonly CollectorPackageRecord[] | null | undefined,
): CollectorPackageRecord[] {
  if (!Array.isArray(packages)) return [];
  return packages
    .filter(isPackage)
    .slice()
    .sort(
      (a, b) =>
        compareText(a.created_at ?? "", b.created_at ?? "") ||
        compareText(a.package_id, b.package_id),
    );
}

/**
 * Two-Collector-snapshot comparison. Compares only when the case really
 * holds two different validated packages from the SAME machine (equal,
 * non-empty hostname hashes) with at least one stored refresh linking a
 * reading in the older package to its re-collection in the newer one.
 * Anything else is an explicit not-comparable state — never a guess.
 */
export function snapshotCompare(inv: InvestigationResponse): LensSnapshot {
  const packages = sortPackages(inv.collector_packages);
  if (packages.length === 0) return { state: "no-packages" };
  if (packages.length === 1) {
    return { state: "single-snapshot", package: packages[0], total: 1 };
  }
  const packageA = packages[packages.length - 2];
  const packageB = packages[packages.length - 1];
  const total = packages.length;
  const hashA = typeof packageA.hostname_hash === "string" ? packageA.hostname_hash : "";
  const hashB = typeof packageB.hostname_hash === "string" ? packageB.hostname_hash : "";
  if (hashA === "" || hashB === "" || hashA !== hashB) {
    return { state: "host-mismatch", packageA, packageB, total };
  }
  const inA = new Set(Array.isArray(packageA.evidence_ids) ? packageA.evidence_ids : []);
  const inB = new Set(Array.isArray(packageB.evidence_ids) ? packageB.evidence_ids : []);
  const byId = new Map<string, EvidenceItem>();
  if (Array.isArray(inv.evidence)) {
    for (const item of inv.evidence) {
      if (isEvidenceItem(item)) byId.set(item.id, item);
    }
  }
  const pairs = sortRefreshes(inv.refreshes)
    .filter(
      (refresh) =>
        inA.has(refresh.old_evidence_id) &&
        typeof refresh.new_evidence_id === "string" &&
        inB.has(refresh.new_evidence_id),
    )
    .map((refresh) => buildPair(refresh, byId));
  if (pairs.length === 0) {
    return { state: "insufficient-evidence", packageA, packageB, total };
  }
  return { state: "compared", packageA, packageB, hostHash: hashA, pairs, total };
}

export function contradictionsFor(
  evidenceId: string,
  contradictions: readonly Contradiction[] | null | undefined,
): Contradiction[] {
  if (!Array.isArray(contradictions)) return [];
  return contradictions.filter(
    (c) => isRecord(c) && Array.isArray(c.evidence_ids) && c.evidence_ids.includes(evidenceId),
  );
}

export type LensCounts = {
  records: number;
  failed: number;
  refreshes: number;
  contradictions: number;
};

/** Counts of local records only — never a confidence score. */
export function lensCounts(inv: InvestigationResponse): LensCounts {
  const records = sortEvidenceRecords(inv.evidence);
  return {
    records: records.length,
    failed: records.filter((item) => recordStatus(item) === "error").length,
    refreshes: sortRefreshes(inv.refreshes).length,
    contradictions: Array.isArray(inv.contradictions) ? inv.contradictions.length : 0,
  };
}
