import { expect, test } from "@playwright/test";
import {
  LENS_MAX_FIELDS,
  buildRefreshPairs,
  comparableData,
  contradictionsFor,
  diffMeasuredFields,
  hostLabel,
  lensCounts,
  recordHost,
  recordStatus,
  shortHostHash,
  snapshotCompare,
  sortEvidenceRecords,
} from "../../src/evidenceLens";
import type {
  CollectorPackageRecord,
  Contradiction,
  EvidenceItem,
  EvidenceRefresh,
  InvestigationResponse,
} from "../../src/types";

/**
 * Evidence Lens logic (M028.B): pure-function contracts over persisted
 * shapes. No browser, no backend — malformed inputs arrive through
 * JSON.parse exactly as wire data would.
 */

function ev(partial: Partial<EvidenceItem> & { id: string }): EvidenceItem {
  return {
    category: "os_info",
    source: "tool:get_os_info:fixture",
    collected_at: "2026-10-31T10:00:00+00:00",
    data: {},
    error: null,
    tool_name: "get_os_info",
    tool_args: {},
    refresh_of: null,
    ...partial,
  };
}

function refresh(
  partial: Partial<EvidenceRefresh> & { old_evidence_id: string },
): EvidenceRefresh {
  return {
    new_evidence_id: null,
    tool_name: "get_os_info",
    verdict: "unchanged",
    changes: [],
    old_collected_at: "2026-10-31T10:00:00+00:00",
    new_collected_at: null,
    compared_at: "2026-10-31T10:05:00+00:00",
    affected_causes: [],
    ...partial,
  };
}

function pkg(partial: Partial<CollectorPackageRecord> & { package_id: string }): CollectorPackageRecord {
  return {
    schema_version: "1.0",
    collector_version: "1.0",
    collector_lang: "python",
    created_at: "2026-10-31T10:00:00+00:00",
    hostname_hash: "aa".repeat(32),
    manifest_sha256: "bb".repeat(32),
    evidence_ids: [],
    warnings: [],
    ...partial,
  };
}

function cx(contradiction_id: string, evidence_ids: string[]): Contradiction {
  return { contradiction_id, evidence_ids, description: `test contradiction ${contradiction_id}` };
}

function inv(partial?: Partial<InvestigationResponse>): InvestigationResponse {
  return {
    investigation_id: "inv-lens",
    problem: "lens probe",
    service_name: null,
    status: "complete",
    created_at: "2026-10-31T10:00:00+00:00",
    uses_fixtures: true,
    analysis_mode: "simulated",
    model: "simulated",
    evidence: [],
    activity: [],
    assessment: null,
    warnings: [],
    has_screenshot: false,
    proposals: [],
    executions: [],
    notes: [],
    refreshes: [],
    plans: [],
    regression_checks: [],
    contradictions: [],
    suggested_rechecks: [],
    tool_calls_used: 0,
    tool_calls_max: 12,
    stage: "INVESTIGATING",
    target: "local",
    understanding: "",
    hypotheses: [],
    plan: null,
    questions: [],
    provider_info: null,
    rounds_used: 0,
    blocked_reason: null,
    assistant_message: "",
    ...partial,
  };
}

test("records sort by collected_at then id, reproducibly", () => {
  const c = ev({ id: "ev-3", collected_at: "2026-10-31T10:02:00+00:00" });
  const a = ev({ id: "ev-1", collected_at: "2026-10-31T10:00:00+00:00" });
  const b = ev({ id: "ev-2", collected_at: "2026-10-31T10:00:00+00:00" });
  const first = sortEvidenceRecords([c, a, b]).map((item) => item.id);
  expect(first).toEqual(["ev-1", "ev-2", "ev-3"]);
  const second = sortEvidenceRecords([b, c, a]).map((item) => item.id);
  expect(second).toEqual(first);
});

test("record sorting drops malformed entries without throwing", () => {
  const wire: EvidenceItem[] = JSON.parse(
    `[${JSON.stringify(ev({ id: "ev-1" }))},null,{},42,"x",[]]`,
  );
  expect(sortEvidenceRecords(wire).map((item) => item.id)).toEqual(["ev-1"]);
  expect(sortEvidenceRecords(null)).toEqual([]);
  expect(sortEvidenceRecords(undefined)).toEqual([]);
});

test("record status covers error/imported/live/fixture/unknown", () => {
  expect(recordStatus(ev({ id: "a", error: "boom" }))).toBe("error");
  expect(recordStatus(ev({ id: "b", error: null, source: "collector:pkg-1:live" }))).toBe("imported");
  expect(recordStatus(ev({ id: "c", error: null, source: "tool:get_os_info:live" }))).toBe("live");
  expect(recordStatus(ev({ id: "d", error: null, source: "tool:get_os_info:fixture" }))).toBe(
    "fixture",
  );
  expect(recordStatus(ev({ id: "e", error: null, source: "screenshot:upload" }))).toBe("unknown");
});

test("record host is grounded: collector hash, local, fixture, unknown", () => {
  const packages = [pkg({ package_id: "pkg-1", evidence_ids: ["ev-1"] })];
  const collector = ev({ id: "ev-1", source: "collector:pkg-1:live" });
  expect(recordHost(collector, inv({ collector_packages: packages }))).toEqual({
    kind: "collector",
    packageId: "pkg-1",
    hostHash: "aa".repeat(32),
  });
  // Unknown package id: the package is named, the host is not invented.
  expect(
    recordHost(ev({ id: "ev-x", source: "collector:pkg-9:live" }), inv({ collector_packages: packages })),
  ).toEqual({ kind: "collector", packageId: "pkg-9", hostHash: null });
  // Live readings ground to this host only on a local-target case.
  const live = ev({ id: "ev-2", source: "tool:get_os_info:live" });
  expect(recordHost(live, inv({ target: "local" }))).toEqual({ kind: "local" });
  expect(recordHost(live, inv({ target: "remote" }))).toEqual({ kind: "unknown" });
  expect(recordHost(ev({ id: "ev-3" }), inv())).toEqual({ kind: "fixture" });
  expect(
    recordHost(ev({ id: "ev-4", source: "screenshot:upload" }), inv()),
  ).toEqual({ kind: "unknown" });
});

test("host labels never expose hostnames", () => {
  expect(shortHostHash("aa".repeat(32))).toBe(`host ${"aa".repeat(6)}…`);
  expect(shortHostHash("")).toBe("unverified host");
  expect(shortHostHash(null)).toBe("unverified host");
  expect(hostLabel({ kind: "fixture" })).toContain("no machine");
  expect(hostLabel({ kind: "local" })).toContain("local case");
});

test("comparable data strips the collector envelope only", () => {
  const data = {
    build: "26100",
    provenance: { collected_at: "2026-10-31T10:00:00+00:00", collector: { package_id: "p" } },
  };
  const cleaned = comparableData(data);
  expect(cleaned.build).toBe("26100");
  expect(JSON.stringify(cleaned)).not.toContain("collector");
  expect(JSON.stringify(cleaned)).toContain("collected_at");
  expect(comparableData(null)).toEqual({});
  expect(comparableData([1, 2])).toEqual({});
});

test("identical readings diff to all-unchanged", () => {
  const data = { caption: "Windows 11", build_number: "26100", nested: { a: 1, b: [1, 2] } };
  const diff = diffMeasuredFields(data, { ...data, nested: { a: 1, b: [1, 2] } });
  expect(diff.changed).toBe(0);
  expect(diff.unknown).toBe(0);
  expect(diff.rows.length).toBe(diff.unchanged);
  expect(diff.rows.every((row) => row.state === "unchanged")).toBe(true);
});

test("changed fields carry before/after paths, sorted", () => {
  const diff = diffMeasuredFields(
    { zebra: 1, build_number: "26100", gone: true },
    { zebra: 1, build_number: "26200", fresh: "x" },
  );
  expect(diff.changed).toBe(3);
  const changed = diff.rows.filter((row) => row.state === "changed");
  expect(changed.map((row) => row.path)).toEqual(["build_number", "fresh", "gone"]);
  const build = changed.find((row) => row.path === "build_number");
  expect(build?.before).toBe('"26100"');
  expect(build?.after).toBe('"26200"');
  expect(changed.find((row) => row.path === "fresh")?.before).toBeNull();
  expect(changed.find((row) => row.path === "gone")?.after).toBeNull();
  // Deterministic across runs.
  expect(JSON.stringify(diff)).toBe(
    JSON.stringify(
      diffMeasuredFields(
        { zebra: 1, build_number: "26100", gone: true },
        { zebra: 1, build_number: "26200", fresh: "x" },
      ),
    ),
  );
});

test("volatile keys and the import envelope never count as changes", () => {
  const before = {
    build_number: "26100",
    summary: "first",
    warnings: ["a"],
    query_ms: 3,
    heartbeat_age_s: 1,
    uptime_s: 5,
    memory_mb: 40,
    timestamp: "t1",
    started: "s1",
    provenance: { collector: { package_id: "p1" } },
  };
  const after = {
    build_number: "26100",
    summary: "second",
    warnings: ["a", "b"],
    query_ms: 99,
    heartbeat_age_s: 50,
    uptime_s: 500,
    memory_mb: 400,
    timestamp: "t2",
    started: "s2",
    provenance: { collector: { package_id: "p2" } },
  };
  const diff = diffMeasuredFields(before, after);
  expect(diff.changed).toBe(0);
  expect(diff.rows.every((row) => row.state === "unchanged")).toBe(true);
});

test("sensitive values are redacted, never rendered", () => {
  const diff = diffMeasuredFields({ api_key: "hunter2", build: "1" }, { api_key: "rotated", build: "1" });
  const row = diff.rows.find((r) => r.path === "api_key");
  // Both sides redact to the same marker: no visible difference, no leak.
  expect(row?.state).toBe("unchanged");
  expect(row?.before).toBe("[redacted]");
  expect(row?.after).toBe("[redacted]");
  const blob = JSON.stringify(diff);
  expect(blob).not.toContain("hunter2");
  expect(blob).not.toContain("rotated");
  // A sensitive key present on one side only still diffs — value redacted.
  const oneSided = diffMeasuredFields({ api_key: "hunter2" }, {});
  const added = oneSided.rows.find((r) => r.path === "api_key");
  expect(added?.state).toBe("changed");
  expect(added?.before).toBe("[redacted]");
  expect(added?.after).toBeNull();
  expect(JSON.stringify(oneSided)).not.toContain("hunter2");
});

test("comparison is bounded: field cap, list cap, depth cap, value cap", () => {
  const big: Record<string, unknown> = {};
  for (let i = 0; i < 300; i += 1) big[`field_${i}`] = i;
  const diff = diffMeasuredFields(big, { ...big, field_0: "changed" });
  expect(diff.truncated).toBe(true);
  expect(diff.rows.length).toBeLessThanOrEqual(LENS_MAX_FIELDS);

  const listed = diffMeasuredFields({ items: Array.from({ length: 30 }, (_, i) => i) }, { items: [] });
  expect(listed.rows.map((row) => row.before)).toContain("[list of 30]");

  let deep: unknown = "leaf";
  for (let i = 0; i < 25; i += 1) deep = { level: deep };
  const deepDiff = diffMeasuredFields({ root: deep }, { root: deep });
  expect(JSON.stringify(deepDiff)).toContain("[nested too deep]");

  const long = diffMeasuredFields({ note: "x".repeat(500) }, { note: "y" });
  const note = long.rows.find((row) => row.path === "note");
  expect(note?.before?.length).toBeLessThanOrEqual(160);
  expect(note?.before?.endsWith("...")).toBe(true);
});

test("malformed records compare as unknown, never throw", () => {
  const wire: Array<{ old: unknown; new: unknown }> = JSON.parse(
    '[{"old":null,"new":{}},{"old":[],"new":"x"},{"old":42,"new":null}]',
  );
  for (const pair of wire) {
    const diff = diffMeasuredFields(pair.old, pair.new);
    expect(diff.unknown).toBe(1);
  }
});

test("refresh pairs link real comparisons with measured diffs", () => {
  const oldItem = ev({ id: "ev-1", data: { build_number: "26100" } });
  const newItem = ev({
    id: "ev-2",
    collected_at: "2026-10-31T10:05:00+00:00",
    data: { build_number: "26200" },
    refresh_of: "ev-1",
  });
  const investigation = inv({
    evidence: [oldItem, newItem],
    refreshes: [
      refresh({
        old_evidence_id: "ev-1",
        new_evidence_id: "ev-2",
        verdict: "changed",
        changes: ["build_number: 26100 -> 26200"],
        new_collected_at: "2026-10-31T10:05:00+00:00",
      }),
    ],
  });
  const pairs = buildRefreshPairs(investigation);
  expect(pairs.length).toBe(1);
  expect(pairs[0].resolution).toBe("ok");
  expect(pairs[0].refreshOfAgrees).toBe(true);
  expect(pairs[0].diff.changed).toBe(1);
  expect(pairs[0].diff.rows[0].path).toBe("build_number");
});

test("failed re-checks resolve as failed-new with no invented fields", () => {
  const investigation = inv({
    evidence: [
      ev({ id: "ev-1", data: { build_number: "26100" } }),
      ev({ id: "ev-2", error: "No fixture data", refresh_of: "ev-1" }),
    ],
    refreshes: [
      refresh({ old_evidence_id: "ev-1", new_evidence_id: "ev-2", verdict: "unavailable" }),
    ],
  });
  const pairs = buildRefreshPairs(investigation);
  expect(pairs[0].resolution).toBe("failed-new");
  expect(pairs[0].diff.rows).toEqual([]);
});

test("missing records resolve as unknown; refresh_of alone invents nothing", () => {
  const investigation = inv({
    evidence: [ev({ id: "ev-1" })],
    refreshes: [refresh({ old_evidence_id: "ev-gone", new_evidence_id: "ev-1" })],
  });
  const pairs = buildRefreshPairs(investigation);
  expect(pairs[0].resolution).toBe("missing-old");
  expect(pairs[0].diff.unknown).toBe(1);

  const orphan = inv({ evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2", refresh_of: "ev-1" })] });
  expect(buildRefreshPairs(orphan)).toEqual([]);
});

test("refresh_of disagreement is flagged, stored verdict kept", () => {
  const investigation = inv({
    evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2", refresh_of: "ev-other" })],
    refreshes: [refresh({ old_evidence_id: "ev-1", new_evidence_id: "ev-2" })],
  });
  const pairs = buildRefreshPairs(investigation);
  expect(pairs[0].refreshOfAgrees).toBe(false);
  expect(pairs[0].refresh.verdict).toBe("unchanged");
});

test("pairs order by compared_at then old id", () => {
  const investigation = inv({
    evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2" }), ev({ id: "ev-3" })],
    refreshes: [
      refresh({ old_evidence_id: "ev-2", compared_at: "2026-10-31T11:00:00+00:00" }),
      refresh({ old_evidence_id: "ev-1", compared_at: "2026-10-31T10:00:00+00:00" }),
    ],
  });
  expect(buildRefreshPairs(investigation).map((p) => p.refresh.old_evidence_id)).toEqual([
    "ev-1",
    "ev-2",
  ]);
});

test("snapshot compare needs two same-host packages with a stored link", () => {
  expect(snapshotCompare(inv())).toEqual({ state: "no-packages" });

  const single = inv({ collector_packages: [pkg({ package_id: "p1" })] });
  const singleOut = snapshotCompare(single);
  expect(singleOut.state).toBe("single-snapshot");
  if (singleOut.state === "single-snapshot") expect(singleOut.package.package_id).toBe("p1");

  const mismatch = inv({
    collector_packages: [
      pkg({ package_id: "p1", evidence_ids: ["ev-1"] }),
      pkg({ package_id: "p2", hostname_hash: "cc".repeat(32), evidence_ids: ["ev-2"] }),
    ],
    evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2", refresh_of: "ev-1" })],
    refreshes: [refresh({ old_evidence_id: "ev-1", new_evidence_id: "ev-2", verdict: "changed" })],
  });
  expect(snapshotCompare(mismatch).state).toBe("host-mismatch");

  const hashless = inv({
    collector_packages: [
      pkg({ package_id: "p1", hostname_hash: "" }),
      pkg({ package_id: "p2", hostname_hash: "" }),
    ],
  });
  expect(snapshotCompare(hashless).state).toBe("host-mismatch");

  const unlinked = inv({
    collector_packages: [
      pkg({ package_id: "p1", evidence_ids: ["ev-1"] }),
      pkg({ package_id: "p2", evidence_ids: ["ev-2"] }),
    ],
    evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2" })],
  });
  expect(snapshotCompare(unlinked).state).toBe("insufficient-evidence");
});

test("snapshot compare links older to newer with explicit identity", () => {
  const investigation = inv({
    collector_packages: [
      pkg({ package_id: "p-old", created_at: "2026-10-30T10:00:00+00:00", evidence_ids: ["ev-1"] }),
      pkg({ package_id: "p-new", created_at: "2026-10-31T10:00:00+00:00", evidence_ids: ["ev-2"] }),
    ],
    evidence: [
      ev({ id: "ev-1", data: { build_number: "26100" } }),
      ev({ id: "ev-2", data: { build_number: "26200" }, refresh_of: "ev-1" }),
    ],
    refreshes: [
      refresh({ old_evidence_id: "ev-1", new_evidence_id: "ev-2", verdict: "changed" }),
    ],
  });
  const out = snapshotCompare(investigation);
  expect(out.state).toBe("compared");
  if (out.state !== "compared") return;
  expect(out.packageA.package_id).toBe("p-old");
  expect(out.packageB.package_id).toBe("p-new");
  expect(out.hostHash).toBe("aa".repeat(32));
  expect(out.pairs.length).toBe(1);
  expect(out.pairs[0].diff.changed).toBe(1);
});

test("three packages compare the two most recent, named explicitly", () => {
  const investigation = inv({
    collector_packages: [
      pkg({ package_id: "p-1", created_at: "2026-10-29T10:00:00+00:00", evidence_ids: ["ev-1"] }),
      pkg({ package_id: "p-2", created_at: "2026-10-30T10:00:00+00:00", evidence_ids: ["ev-2"] }),
      pkg({ package_id: "p-3", created_at: "2026-10-31T10:00:00+00:00", evidence_ids: ["ev-3"] }),
    ],
    evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2" }), ev({ id: "ev-3" })],
    refreshes: [refresh({ old_evidence_id: "ev-2", new_evidence_id: "ev-3" })],
  });
  const out = snapshotCompare(investigation);
  expect(out.state).toBe("compared");
  if (out.state !== "compared") return;
  expect(out.packageA.package_id).toBe("p-2");
  expect(out.packageB.package_id).toBe("p-3");
  expect(out.total).toBe(3);
});

test("contradictions map to citing records only", () => {
  const list = [cx("cx-1", ["ev-1", "ev-2"]), cx("cx-2", ["ev-2"])];
  expect(contradictionsFor("ev-1", list).map((c) => c.contradiction_id)).toEqual(["cx-1"]);
  expect(contradictionsFor("ev-2", list).map((c) => c.contradiction_id)).toEqual(["cx-1", "cx-2"]);
  expect(contradictionsFor("ev-9", list)).toEqual([]);
  expect(contradictionsFor("ev-1", null)).toEqual([]);
});

test("lens counts are local record counts", () => {
  const counts = lensCounts(
    inv({
      evidence: [ev({ id: "ev-1" }), ev({ id: "ev-2", error: "x" })],
      refreshes: [refresh({ old_evidence_id: "ev-1" })],
      contradictions: [cx("cx-1", ["ev-1"])],
    }),
  );
  expect(counts).toEqual({ records: 2, failed: 1, refreshes: 1, contradictions: 1 });
});

test("large-record diff stays bounded and fast", () => {
  const record: Record<string, unknown> = {};
  for (let i = 0; i < 150; i += 1) record[`field_${i}`] = `value-${i}-`.repeat(6);
  const started = Date.now();
  const first = diffMeasuredFields(record, { ...record, field_7: "different" });
  const second = diffMeasuredFields(record, { ...record, field_7: "different" });
  const elapsed = Date.now() - started;
  expect(first.changed).toBe(1);
  expect(JSON.stringify(first)).toBe(JSON.stringify(second));
  expect(elapsed).toBeLessThan(2000);
});
