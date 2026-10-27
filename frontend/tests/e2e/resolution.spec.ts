import { expect, test } from "@playwright/test";

test("guided resolution runs to an honest measured outcome", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: the FieldRook demo worker is down.",
  );
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });

  await expect(page.getByText("Resolution workspace")).toBeVisible();
  await page.getByRole("button", { name: "New resolution plan" }).click();
  await page.getByRole("button", { name: "Use demo-worker recovery template" }).click();
  // Template prefilled two measurable criteria.
  await expect(page.getByText("Criterion 2")).toBeVisible();
  await page.getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });

  await page.getByRole("button", { name: "Capture pre-fix baseline" }).click();
  await expect(page.getByText("BASELINED", { exact: true }).first()).toBeVisible({ timeout: 15000 });

  // A manual claim alone proves nothing: no outcome yet.
  await page.getByPlaceholder(/What did you do by hand/).fill("Restarted the worker by hand.");
  await page.getByRole("button", { name: "Record manual fix" }).click();
  await expect(page.getByText("INTERVENED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("MANUAL CLAIM")).toBeVisible();

  // Fixtures still report failing: the honest outcome is NOT_RESOLVED.
  await page.getByRole("button", { name: "Confirm Fix" }).click();
  await expect(page.getByText("NOT_RESOLVED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Recommended next step")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-resolution.png", fullPage: true });
});

test("resolution plan survives reopen from history", async ({ page }) => {
  await page.goto("/");
  const probe = `E2E resolution probe ${Date.now()}`;
  await page.getByPlaceholder(/vpn disconnects/i).fill(`${probe}: the demo worker is down.`);
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("Resolution workspace")).toBeVisible({ timeout: 30000 });

  await page.getByRole("button", { name: "New resolution plan" }).click();
  await page.getByRole("button", { name: "Use demo-worker recovery template" }).click();
  await page.getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });

  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  await page.getByText(probe).first().click();
  await expect(page.getByText("Resolution workspace")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });
});
