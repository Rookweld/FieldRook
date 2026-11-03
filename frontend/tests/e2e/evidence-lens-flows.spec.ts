/**
 * M028.D (preserved from m028/delta-demo): Evidence Lens flows pinned to
 * engine/SIGNALFORGE DOM + API contracts. Renamed from evidence-lens.spec.ts
 * to evidence-lens-flows.spec.ts at merge to keep both builders' suites.
 */
import { expect, test, type Page } from "@playwright/test";

/**
 * M028.D — Evidence Lens flows, pinned against the DOM/contracts this branch
 * actually ships (engine Evidence tab, SIGNALFORGE Evidence view, reverify
 * + export endpoints). The M028 Lens instrument re-skins these flows; the
 * merge lead owns selector drift, but every behaviour below must survive:
 * deterministic record order, original-vs-recheck comparison through
 * refresh_of/refreshes linkage, contradiction citations, no false diffs.
 */

const BACKEND = "http://127.0.0.1:8123";
const NETWORK_PROBLEM =
  "E2E lens probe: the network is down on this machine, I am sure the cable is unplugged.";

async function investigateFixture(page: Page, problem: string) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(problem);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible({ timeout: 30000 });
}

test("lens lists records deterministically with source, tool, and timestamps", async ({
  page,
}) => {
  await investigateFixture(page, NETWORK_PROBLEM);
  await page.getByRole("tab", { name: /Evidence/ }).click();

  // One deterministic group; cards arrive in collection order ev-1..ev-3.
  await expect(page.getByRole("heading", { name: /Network \(3\)/ })).toBeVisible();
  const ids = await page
    .locator(".view-panel .evidence-list article")
    .evaluateAll((els) => els.map((e) => e.id));
  expect(ids).toEqual(["evcard-ev-1", "evcard-ev-2", "evcard-ev-3"]);

  // Provenance on each card: category, tool source, collection time.
  const first = page.locator("#evcard-ev-1");
  await expect(first.getByText("net_adapters", { exact: true })).toBeVisible();
  await expect(first.getByText("tool:get_network_adapters:fixture")).toBeVisible();
  await expect(page.locator("#evcard-ev-2").getByText("tool:get_ip_config:fixture")).toBeVisible();
  await expect(page.locator("#evcard-ev-3").getByText("tool:get_dns_config:fixture")).toBeVisible();

  // Single snapshot: no comparison chrome may appear (no false diff).
  await expect(page.locator(".view-panel").getByText("HISTORICAL")).toHaveCount(0);
  await expect(page.locator(".view-panel").getByText("RE-CHECK OF")).toHaveCount(0);
  await expect(page.getByText("Evidence changes between rounds")).toHaveCount(0);

  // SIGNALFORGE Evidence view mirrors the same case: count, records, detail.
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  const view = page.locator('section[aria-label="Evidence"]');
  // Header count lives outside the Lens (the merged M028.B instrument repeats
  // the count inside its own panel, so scope to the header paragraph).
  await expect(view.locator(".sf-utility > p").first()).toContainText("3 records on this case");
  // No re-check records yet: the legacy Re-checks card is absent and the Lens
  // shows its empty state (merged M028.B instrument renders "Re-checks (0)").
  await expect(view.getByText("No re-checks yet")).toBeVisible();
  await expect(view.getByText(/Re-checks \([1-9]/)).toHaveCount(0);
  const detail = view.locator(".sf-ev-detail");
  await expect(detail.getByText("ev-1", { exact: true })).toBeVisible();
  await expect(detail.getByText("get_network_adapters", { exact: true }).first()).toBeVisible();
});

test("lens compares an original reading with its re-check (unchanged)", async ({
  page,
  request,
}) => {
  await investigateFixture(page, NETWORK_PROBLEM);
  const investigationId = (await page.locator(".contextbar-meta").innerText()).split("·")[0].trim();
  expect(investigationId.length).toBeGreaterThan(0);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await page.locator("#evcard-ev-1").getByRole("button", { name: "Re-check", exact: true }).click();

  // Linkage flags: new card points back, old card is marked superseded.
  // (Scoped + exact: the timeline echoes "Re-check of ev-1 …" as prose.)
  const fresh = page.locator("#evcard-ev-4");
  await expect(fresh.getByText("RE-CHECK OF ev-1", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/HISTORICAL.*SUPERSEDED BY ev-4.*UNCHANGED/)).toBeVisible();

  // RefreshPanel renders the verdict with the real tool name and timestamps.
  // (Scoped to the refresh row: cards and timeline repeat the tool name.)
  await expect(page.getByText("Evidence changes between rounds")).toBeVisible();
  const row = page.locator("li.refresh").first();
  await expect(row.getByText("UNCHANGED", { exact: true })).toBeVisible();
  await expect(row.getByText("get_network_adapters", { exact: true })).toBeVisible();
  await expect(row.getByText(/Historical:/)).toBeVisible();

  // SIGNALFORGE Evidence view carries the same re-check record.
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  // Both the legacy Re-checks card and the merged Lens carry the record;
  // scope to the legacy card (the only surface rendering "tool: verdict").
  const legacyRechecks = page
    .locator('section[aria-label="Evidence"] .sf-utility-card', {
      hasText: /get_network_adapters: unchanged/,
    })
    .first();
  await expect(legacyRechecks.getByRole("heading", { name: "Re-checks (1)" })).toBeVisible();
  await expect(legacyRechecks.getByText(/get_network_adapters: unchanged/)).toBeVisible();

  // The exported report preserves the comparison for the ticket.
  const md = await request.get(`${BACKEND}/api/investigations/${investigationId}/export?format=markdown`);
  expect(md.ok()).toBeTruthy();
  const text = await md.text();
  expect(text).toContain("## 14. Evidence refresh history");
  expect(text).toContain("ev-1 -> ev-4: UNCHANGED");
  expect(text).toContain("Tool: get_network_adapters");
});

test("lens surfaces contradictions cited to real evidence ids", async ({ page }) => {
  await investigateFixture(page, NETWORK_PROBLEM);

  // Findings tab: ProgressPanel names the conflict and cites ev-1.
  const progress = page.locator(".view-panel", { has: page.getByText("Investigation progress") });
  await expect(progress.getByText("Contradictions (1)")).toBeVisible({ timeout: 15000 });
  const conflict = progress.locator(".contradiction");
  await expect(conflict.getByText("CONFLICT")).toBeVisible();
  await expect(conflict.getByText(/measurement \(ev-1\) shows adapter/)).toBeVisible();
  const chip = conflict.getByRole("button", { name: "ev-1", exact: true });
  await expect(chip).toBeVisible();

  // Chip drill-through: quick preview, then jump to the full record.
  await chip.click();
  const peek = page.getByRole("region", { name: "Evidence ev-1 quick view" });
  await expect(peek).toBeVisible();
  await expect(peek.getByText("tool:get_network_adapters:fixture")).toBeVisible();
  await peek.getByRole("button", { name: "Go to full evidence" }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#evcard-ev-1")).toBeVisible();

  // The suggested re-check for the disputed reading runs from Findings.
  await page.getByRole("tab", { name: "Findings", exact: true }).click();
  await progress.getByRole("button", { name: "Re-check now" }).click();
  await expect(progress.getByText("1 re-check")).toBeVisible({ timeout: 15000 });
});

test("lens refresh linkage contract: refresh_of, verdicts, affected causes", async ({
  request,
}) => {
  const created = await request.post(`${BACKEND}/api/investigations`, {
    multipart: {
      problem: "Lens contract probe: the network is down on this machine.",
      use_fixtures: "true",
      share_consent: "true",
    },
  });
  expect(created.ok()).toBeTruthy();
  const inv = (await created.json()) as {
    investigation_id: string;
    evidence: Array<{ id: string; refresh_of: string | null }>;
  };
  expect(inv.evidence.map((e) => e.id)).toEqual(["ev-1", "ev-2", "ev-3"]);

  const reverified = await request.post(
    `${BACKEND}/api/investigations/${inv.investigation_id}/reverify`,
    { data: { evidence_id: "ev-1" } },
  );
  expect(reverified.ok()).toBeTruthy();
  const body = (await reverified.json()) as {
    evidence: Array<{ id: string; refresh_of: string | null; tool_name: string | null }>;
    refreshes: Array<{
      old_evidence_id: string;
      new_evidence_id: string | null;
      tool_name: string;
      verdict: string;
      changes: string[];
      affected_causes: string[];
    }>;
  };
  const fresh = body.evidence.find((e) => e.id === "ev-4");
  expect(fresh?.refresh_of).toBe("ev-1");
  expect(fresh?.tool_name).toBe("get_network_adapters");
  expect(body.refreshes).toHaveLength(1);
  const [refresh] = body.refreshes;
  expect(refresh.old_evidence_id).toBe("ev-1");
  expect(refresh.new_evidence_id).toBe("ev-4");
  expect(["changed", "unchanged", "unavailable"]).toContain(refresh.verdict);
  expect(refresh.verdict).toBe("unchanged");
  expect(refresh.changes).toEqual([]);
  expect(Array.isArray(refresh.affected_causes)).toBeTruthy();
});
