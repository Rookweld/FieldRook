import { expect, test } from "@playwright/test";

test("guided resolution runs to an honest measured outcome", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: the FieldRook demo worker is down.",
  );
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });

  await page.getByRole("tab", { name: "Resolve" }).click();
  await expect(page.getByRole("heading", { name: /Resolution workspace/ })).toBeVisible();
  await page.locator(".view-panel").getByRole("button", { name: "New resolution plan" }).click();
  await page.locator(".view-panel").getByRole("button", { name: "Use demo-worker recovery template" }).click();
  // Template prefilled two measurable criteria.
  await expect(page.getByText("Criterion 2")).toBeVisible();
  await page.locator(".view-panel").getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });

  await page.locator(".view-panel").getByRole("button", { name: "Capture pre-fix baseline" }).click();
  await expect(page.getByText("BASELINED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  // M010-7: the pre-fix baseline run is its own timeline round.
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("pre-fix baseline").first()).toBeVisible();
  await page.getByRole("tab", { name: "Resolve" }).click();

  // A manual claim alone proves nothing: no outcome yet.
  await page.getByPlaceholder(/What did you do by hand/).fill("Restarted the worker by hand.");
  await page.locator(".view-panel").getByRole("button", { name: "Record manual fix" }).click();
  await expect(page.getByText("INTERVENED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("MANUAL CLAIM")).toBeVisible();

  // Fixtures still report failing: the honest outcome is NOT_RESOLVED.
  await page.locator(".view-panel").getByRole("button", { name: "Confirm Fix" }).click();
  await expect(page.getByText("NOT_RESOLVED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  // M010-2/3: the Findings header follows the plan outcome.
  await page.getByRole("tab", { name: "Findings" }).click();
  await expect(page.getByText("UNRESOLVED — verified outcome: NOT_RESOLVED")).toBeVisible();
  // M012: views navigate between finding, evidence, and resolution.
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("pre-fix baseline").first()).toBeVisible();
  await page.getByRole("tab", { name: "Resolve" }).click();
  await expect(page.getByText("Recommended next step")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-resolution.png", fullPage: true });
});

test("resolution plan survives reopen from history", async ({ page }) => {
  await page.goto("/");
  const probe = `E2E resolution probe ${Date.now()}`;
  await page.getByPlaceholder(/vpn disconnects/i).fill(`${probe}: the demo worker is down.`);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await page.getByRole("tab", { name: "Resolve" }).click();
  await expect(page.getByRole("heading", { name: /Resolution workspace/ })).toBeVisible({ timeout: 30000 });

  await page.locator(".view-panel").getByRole("button", { name: "New resolution plan" }).click();
  await page.locator(".view-panel").getByRole("button", { name: "Use demo-worker recovery template" }).click();
  await page.locator(".view-panel").getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });

  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Launchpad", exact: true }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  await page.getByText(probe).first().click();
  await page.getByRole("tab", { name: "Resolve" }).click();
  await expect(page.getByRole("heading", { name: /Resolution workspace/ })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });
});
