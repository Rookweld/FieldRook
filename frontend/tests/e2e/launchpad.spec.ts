import { expect, test } from "@playwright/test";

// Fresh profiles (no persisted view state) land on the SIGNALFORGE
// launchpad. Every other spec runs workbench-first via the shared
// storageState seed; this spec pins the new default + primary nav.
test.use({ storageState: { cookies: [], origins: [] } });

test("launchpad is the fresh landing with working nav and recents", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /be curious/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "New investigation" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Launchpad", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Workbench", exact: true })).toBeVisible();

  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Workbench", exact: true }).click();
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toBeVisible();

  const probe = `E2E launchpad probe ${Date.now()}`;
  await page.getByPlaceholder(/vpn disconnects/i).fill(probe);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({ timeout: 30000 });

  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Launchpad", exact: true }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  await page.getByText(probe).first().click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: "test-results/shot-launchpad.png" });
});
