import type { DiagnosisTarget, EvidenceItem, InvestigationResponse } from "../types";

/**
 * M028.C Network Lab — pure selectors and guards over persisted evidence.
 *
 * The lab surfaces ONLY records already on the case plus re-checks through
 * the existing POST .../reverify path (see useNetworkLab). Tool names here
 * must stay within the backend registry allowlist:
 * get_network_adapters, get_ip_config, get_dns_config, get_connections,
 * test_dns_resolution. There is intentionally no ping, traceroute, or
 * port-scan concept anywhere in this module.
 */

export type NetworkCategory =
  | "net_adapters"
  | "ip_config"
  | "dns_config"
  | "connections"
  | "dns_test";

export type NetworkToolName =
  | "get_network_adapters"
  | "get_ip_config"
  | "get_dns_config"
  | "get_connections"
  | "test_dns_resolution";

export type NetworkSectionSpec = {
  category: NetworkCategory;
  tool: NetworkToolName;
  title: string;
  blurb: string;
  activeTest: boolean;
};

/** Fixed display order; every shipped network category appears exactly once. */
export const NETWORK_SECTIONS: readonly NetworkSectionSpec[] = [
  {
    category: "net_adapters",
    tool: "get_network_adapters",
    title: "Adapters",
    blurb: "Adapter status, link speed, and MAC addresses.",
    activeTest: false,
  },
  {
    category: "ip_config",
    tool: "get_ip_config",
    title: "IP configuration",
    blurb: "Configured IP addresses per interface.",
    activeTest: false,
  },
  {
    category: "dns_config",
    tool: "get_dns_config",
    title: "DNS configuration",
    blurb: "Configured DNS servers per interface.",
    activeTest: false,
  },
  {
    category: "connections",
    tool: "get_connections",
    title: "Connections",
    blurb: "Bounded sample of established TCP connections at collection time.",
    activeTest: false,
  },
  {
    category: "dns_test",
    tool: "test_dns_resolution",
    title: "DNS resolution tests",
    blurb: "Single-query A/AAAA lookups. Each test sends one real DNS query.",
    activeTest: true,
  },
];

export type NetworkSection = NetworkSectionSpec & {
  /** Deterministic order: collected_at, then id. */
  items: EvidenceItem[];
  latest: EvidenceItem | null;
};

export function networkSections(investigation: InvestigationResponse | null): NetworkSection[] {
  const evidence = investigation?.evidence ?? [];
  return NETWORK_SECTIONS.map((spec) => {
    const items = evidence
      .filter((item) => item.category === spec.category)
      .slice()
      .sort((a, b) =>
        a.collected_at < b.collected_at
          ? -1
          : a.collected_at > b.collected_at
            ? 1
            : a.id < b.id
              ? -1
              : a.id > b.id
                ? 1
                : 0,
      );
    return { ...spec, items, latest: items.length > 0 ? items[items.length - 1] : null };
  });
}

export type SourceOrigin = "tool-host" | "collector" | "other";
export type SourceProvenance = "live" | "fixture" | "unknown";

export type ParsedSource = {
  origin: SourceOrigin;
  provenance: SourceProvenance;
  /** Registered tool name when the source string carries one. */
  tool: string | null;
  /** Short honest badge text, e.g. "LIVE", "FIXTURE", "COLLECTOR", "UNKNOWN". */
  badge: string;
};

/**
 * Parse backend source strings. Host tools record
 * `tool:<name>:<live|fixture>`; Collector imports record
 * `collector:<package>:<suffix>`. Anything else is "other/unknown" —
 * never upgraded to a stronger claim.
 */
export function parseSource(source: string | null | undefined): ParsedSource {
  if (typeof source === "string" && source.startsWith("collector:")) {
    return { origin: "collector", provenance: "unknown", tool: null, badge: "COLLECTOR" };
  }
  if (typeof source === "string" && source.startsWith("tool:")) {
    const parts = source.split(":");
    const tool = parts.length > 1 && parts[1] !== "" ? parts[1] : null;
    const tail = parts.length > 2 ? parts[parts.length - 1] : "";
    const provenance: SourceProvenance =
      tail === "live" ? "live" : tail === "fixture" ? "fixture" : "unknown";
    return {
      origin: "tool-host",
      provenance,
      tool,
      badge: provenance === "live" ? "LIVE" : provenance === "fixture" ? "FIXTURE" : "UNKNOWN",
    };
  }
  return { origin: "other", provenance: "unknown", tool: null, badge: "UNKNOWN" };
}

export type RecheckAvailability = { allowed: true } | { allowed: false; reason: string };

const NETWORK_TOOL_NAMES: ReadonlySet<string> = new Set(NETWORK_SECTIONS.map((s) => s.tool));

/**
 * Client-side mirror of the backend reverify guards (HTTP 422/409). The
 * server re-enforces every rule; this only keeps the UI honest so a
 * technician never sees a working-looking Run button that must fail.
 */
export function recheckAvailability(
  item: EvidenceItem,
  target: DiagnosisTarget,
): RecheckAvailability {
  if (!item.tool_name || item.tool_args === null || !NETWORK_TOOL_NAMES.has(item.tool_name)) {
    return {
      allowed: false,
      reason: "No re-runnable tool provenance on this record.",
    };
  }
  if ((item.source ?? "").startsWith("collector:")) {
    return {
      allowed: false,
      reason:
        "Imported from another computer — import a fresh Collector package from the affected machine to compare.",
    };
  }
  if (target !== "local") {
    return {
      allowed: false,
      reason: `Case target is '${target}': measuring this host would misattribute the reading to the affected computer.`,
    };
  }
  return { allowed: true };
}

/** Human target banner copy; never claims a measurement the case lacks. */
export function targetBanner(target: DiagnosisTarget): { heading: string; body: string } {
  switch (target) {
    case "local":
      return {
        heading: "Local target — this computer",
        body: "Host readings below describe the machine running FieldRook. Re-checks re-run the exact registered tool call with your explicit consent.",
      };
    case "remote":
      return {
        heading: "Remote target — another computer",
        body: "Records below are existing observations only. This host is never measured as if it were the affected computer — import a Collector package from that machine instead.",
      };
    case "unknown":
      return {
        heading: "Unknown target — not established",
        body: "It is not established which computer is affected. Host readings below are host-only and must not be treated as evidence about another machine.",
      };
  }
}

/* ------------------------------------------------------------------ */
/* Defensive record readers. Unknown, truncated, or malformed shapes  */
/* degrade to "not shown" rows — never to invented values.            */
/* ------------------------------------------------------------------ */

export const MAX_ROWS = 25;
export const MAX_TEXT = 220;

export function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function text(value: unknown): string | null {
  if (typeof value === "string" && value !== "") return value.slice(0, MAX_TEXT);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

export function isTruncated(data: Record<string, unknown>): boolean {
  return data["_truncated"] === true;
}
