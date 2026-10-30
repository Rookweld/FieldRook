import { expect, test } from "@playwright/test";

const legacyInvestigation = {
  investigation_id: "inv-legacy-test",
  problem: "Compatibility test",
  service_name: null,
  status: "complete",
  created_at: "2026-10-27T00:00:00Z",
  uses_fixtures: true,
  analysis_mode: "simulated",
  model: "fieldrook-simulated-001",
  evidence: [],
  activity: [],
  assessment: null,
  warnings: [],
  has_screenshot: false,
  proposals: [],
  executions: [],
  // Deliberately omit M007–M009 fields to simulate a stale Python server.
};

test("outdated backend is reported rather than crashing after Investigate", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/investigations", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: legacyInvestigation });
    } else {
      await route.continue();
    }
  });
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill("Investigate a service issue");
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  await expect(page.getByRole("alert")).toContainText("frontend/backend version mismatch");
  await expect(page.getByRole("button", { name: "Launchpad", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("outdated backend is reported rather than crashing when opening History", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route(/\/api\/investigations\?limit=/, async (route) => {
    await route.fulfill({
      json: [{
        investigation_id: "inv-legacy-test",
        problem: "Compatibility test",
        status: "complete",
        created_at: "2026-10-27T00:00:00Z",
        updated_at: "2026-10-27T00:00:00Z",
        evidence_count: 0,
        proposal_count: 0,
      }],
    });
  });
  await page.route("**/api/investigations/inv-legacy-test", async (route) => {
    await route.fulfill({ json: legacyInvestigation });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Launchpad", exact: true }).click();
  await page.getByRole("button", { name: "Compatibility test" }).click();

  await expect(page.getByText(/Open failed.*frontend\/backend version mismatch/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Launchpad", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
