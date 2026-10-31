import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

/**
 * Evidence Lens E2E (M028.B): the mounted instrument over real backend
 * state. Cases are built through the production API (investigate,
 * reverify, import-collector); collector ZIPs are built through the real
 * collector manifest/archive path. No fixtures are smuggled into the UI.
 */

const API = "http://127.0.0.1:8123";
const specDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(specDir, "..", "..", "..");
const backendDir = path.join(repoRoot, "backend");
const localVenv = path.join(backendDir, ".venv", "Scripts", "python.exe");
const devVenv = "C:\\dev\\FieldRook\\backend\\.venv\\Scripts\\python.exe";
const pythonExe = fs.existsSync(localVenv) ? localVenv : devVenv;
const helper = path.join(specDir, "helpers", "make_pkg.py");

const HOST_A = "ab".repeat(32);
const HOST_B = "cd".repeat(32);

type EvidenceRow = {
  id: string;
  category: string;
  collected_at: string;
  tool_name: string | null;
  source: string;
  error: string | null;
};

type RefreshRow = {
  old_evidence_id: string;
  new_evidence_id: string | null;
  tool_name: string;
  verdict: string;
};

type Investigation = {
  investigation_id: string;
  problem: string;
  evidence: EvidenceRow[];
  refreshes: RefreshRow[];
  contradictions: Array<{ contradiction_id: string; evidence_ids: string[]; description: string }>;
  collector_packages: Array<{ package_id: string; hostname_hash: string; evidence_ids: string[] }>;
};

async function createCase(
  request: APIRequestContext,
  problem: string,
  extra: Record<string, string> = {},
): Promise<Investigation> {
  const res = await request.post(`${API}/api/investigations`, {
    form: { problem, share_consent: "true", ...extra },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()) as Investigation;
}

async function readCase(request: APIRequestContext, id: string): Promise<Investigation> {
  const res = await request.get(`${API}/api/investigations/${id}`);
  expect(res.ok()).toBe(true);
  return (await res.json()) as Investigation;
}

async function openLens(page: Page, probe: string): Promise<void> {
  await page.goto("/");
  const primary = page.getByRole("navigation", { name: "Primary" });
  await primary.getByRole("button", { name: "Launchpad", exact: true }).click();
  await page.getByText(probe).first().click();
  await primary.getByRole("button", { name: "Evidence", exact: true }).click();
  await expect(page.getByTestId("evidence-lens")).toBeVisible();
}

function makePackage(
  info: TestInfo,
  name: string,
  hostHash: string,
  entries: unknown[],
  createdAt: string,
): { zip: string; packageId: string } {
  fs.mkdirSync(info.outputDir, { recursive: true });
  const specPath = path.join(info.outputDir, `${name}.entries.json`);
  fs.writeFileSync(specPath, JSON.stringify(entries));
  const zip = path.join(info.outputDir, `${name}.zip`);
  const packageId = execFileSync(
    pythonExe,
    [
      helper,
      "--out",
      zip,
      "--host-hash",
      hostHash,
      "--entries",
      specPath,
      "--created-at",
      createdAt,
    ],
    { encoding: "utf-8" },
  ).trim();
  expect(packageId.length).toBeGreaterThan(0);
  return { zip, packageId };
}

async function importPackage(request: APIRequestContext, invId: string, zip: string) {
  return request.post(`${API}/api/investigations/${invId}/import-collector`, {
    multipart: {
      file: { name: path.basename(zip), mimeType: "application/zip", buffer: fs.readFileSync(zip) },
      share_consent: "true",
    },
  });
}

function osEntry(build: string) {
  return {
    id: "c-os",
    category: "os_info",
    data: { caption: "Microsoft Windows 11 Pro", version: "10.0.26100", build_number: build },
    tool_name: "get_os_info",
    tool_args: {},
  };
}

function dnsEntry() {
  return {
    id: "c-dns",
    category: "dns_config",
    data: { interfaces: [{ interface: "Wi-Fi", servers: ["192.168.1.1"] }] },
    tool_name: "get_dns_config",
    tool_args: {},
  };
}

test("lens lists records deterministically with provenance", async ({ page, request }) => {
  const probe = `Lens records probe ${Date.now()} VPN disconnects every 10 minutes`;
  const created = await createCase(request, probe);
  expect(created.evidence.length).toBeGreaterThan(0);

  await openLens(page, probe);

  const current = await readCase(request, created.investigation_id);
  const rows = page.getByTestId("lens-record-row");
  await expect(rows).toHaveCount(current.evidence.length);
  const uiIds = await rows.evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-record-id")),
  );
  const expected = current.evidence
    .slice()
    .sort((a, b) => {
      if (a.collected_at !== b.collected_at) return a.collected_at < b.collected_at ? -1 : 1;
      return a.id < b.id ? -1 : 1;
    })
    .map((item) => item.id);
  expect(uiIds).toEqual(expected);

  const first = rows.first();
  const firstApi = current.evidence.find((item) => item.id === expected[0]);
  await expect(first).toContainText(firstApi?.tool_name ?? firstApi?.category ?? "");
  await expect(first).toContainText("FIXTURE");
  await expect(first).toContainText("fixture (no machine)");

  // Reproducible across sessions: reopen and compare the full order.
  await openLens(page, probe);
  const uiIdsAgain = await page.getByTestId("lens-record-row").evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-record-id")),
  );
  expect(uiIdsAgain).toEqual(expected);
});

test("unchanged re-check pair shows verdict, ids, and measured fields", async ({
  page,
  request,
}) => {
  const probe = `Lens reverify probe ${Date.now()} DNS does not resolve anything`;
  const created = await createCase(request, probe);
  const old = created.evidence.find((item) => item.category === "dns_config");
  expect(old?.id).toBeTruthy();

  const res = await request.post(
    `${API}/api/investigations/${created.investigation_id}/reverify`,
    { data: { evidence_id: old?.id ?? "" } },
  );
  expect(res.ok()).toBe(true);
  const again = (await res.json()) as Investigation;
  expect(again.refreshes.length).toBe(1);
  const refresh = again.refreshes[0];
  expect(refresh.verdict).toBe("unchanged");

  await openLens(page, probe);

  const section = page.getByTestId("lens-refreshes");
  await expect(section.getByText("UNCHANGED", { exact: true })).toBeVisible();
  await expect(section.getByText(refresh.old_evidence_id, { exact: true }).first()).toBeVisible();
  await expect(
    section.getByText(refresh.new_evidence_id ?? "", { exact: true }).first(),
  ).toBeVisible();
  await expect(section).toContainText("Measured fields");
  await expect(section).toContainText("No measured field differs");
  await expect(section.getByText("CHANGED", { exact: true })).toHaveCount(0);
});

test("two same-host snapshots compare with explicit identity", async ({
  page,
  request,
}, info) => {
  const probe = `Lens snapshot probe ${Date.now()} remote workstation review`;
  const created = await createCase(request, probe, { target: "remote" });

  const a = makePackage(info, "snap-a", HOST_A, [osEntry("26100"), dnsEntry()], "2026-10-30T10:00:00+00:00");
  const b = makePackage(info, "snap-b", HOST_A, [osEntry("26200"), dnsEntry()], "2026-10-31T10:00:00+00:00");
  expect((await importPackage(request, created.investigation_id, a.zip)).ok()).toBe(true);
  expect((await importPackage(request, created.investigation_id, b.zip)).ok()).toBe(true);
  const after = await readCase(request, created.investigation_id);
  expect(after.refreshes.length).toBe(2);

  await openLens(page, probe);

  const section = page.getByTestId("lens-snapshots");
  await expect(section).toContainText(a.packageId);
  await expect(section).toContainText(b.packageId);
  await expect(section).toContainText(`host ${"ab".repeat(6)}…`);
  await expect(section).toContainText("2 linked readings");
  await expect(section.getByText("CHANGED", { exact: true })).toBeVisible();
  await expect(section.getByText("UNCHANGED", { exact: true })).toBeVisible();
  await expect(section).toContainText("build_number");

  // Drill through: an old-evidence id opens the existing inspector on it.
  const oldId = after.collector_packages[0].evidence_ids[0];
  await section.getByRole("button", { name: `Inspect record ${oldId}` }).first().click();
  await expect(page.locator(".sf-ev-detail").getByText(oldId, { exact: true })).toBeVisible();
});

test("single snapshot shows insufficient evidence; mismatched host rejected", async ({
  page,
  request,
}, info) => {
  const probe = `Lens single probe ${Date.now()} remote workstation review`;
  const created = await createCase(request, probe, { target: "remote" });

  const a = makePackage(
    info,
    "single-a",
    HOST_A,
    [
      osEntry("26100"),
      {
        id: "c-err",
        category: "service_list",
        data: {},
        tool_name: "list_services",
        tool_args: {},
        error: "simulated collector fault",
      },
    ],
    "2026-10-30T10:00:00+00:00",
  );
  const other = makePackage(info, "single-b", HOST_B, [osEntry("26100")], "2026-10-31T10:00:00+00:00");
  expect((await importPackage(request, created.investigation_id, a.zip)).ok()).toBe(true);
  const rejected = await importPackage(request, created.investigation_id, other.zip);
  expect(rejected.status()).toBe(409);

  await openLens(page, probe);

  const section = page.getByTestId("lens-snapshots");
  await expect(section).toContainText("Only one Collector snapshot");
  await expect(section).toContainText(a.packageId);
  await expect(section).toContainText("No differences are inferred");
  await expect(section.getByTestId("lens-pair")).toHaveCount(0);

  const records = page.getByTestId("lens-records");
  await expect(records).toContainText("1 failed to collect");
  await expect(records.getByText("ERROR", { exact: true }).first()).toBeVisible();
});

test("contradictions highlight with real cited evidence ids", async ({ page, request }) => {
  const probe = `Lens contradiction probe ${Date.now()} the network is down no connectivity at all`;
  const created = await createCase(request, probe);
  expect(created.contradictions.length).toBeGreaterThan(0);
  const cited = created.contradictions[0].evidence_ids[0];

  await openLens(page, probe);

  const section = page.getByTestId("lens-contradictions");
  await expect(section).toContainText("Trust the measurement");
  await expect(section.getByRole("button", { name: `Inspect record ${cited}` })).toBeVisible();
  await expect(page.getByTestId("lens-records")).toContainText("cited by 1 contradiction");

  await section.getByRole("button", { name: `Inspect record ${cited}` }).click();
  await expect(page.locator(".sf-ev-detail").getByText(cited, { exact: true })).toBeVisible();
});
