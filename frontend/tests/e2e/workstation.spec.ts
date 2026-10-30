import { expect, test } from "@playwright/test";

test("workstation opens with brand, views, and tabs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Launchpad", exact: true })).toBeVisible();
  await expect(page.getByText("Diagnose. Verify. Resolve.").first()).toBeVisible();
  // SIGNALFORGE primary nav.
  await expect(page.getByRole("button", { name: "Workbench", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Evidence", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Settings", exact: true })).toBeVisible();
  // Intake form with one prominent action.
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Investigate", exact: true })).toBeVisible();

  // An active investigation gains Findings / Evidence / Resolve views plus
  // a result header with one obvious next step.
  await page.getByPlaceholder(/vpn disconnects/i).fill("E2E probe: DNS does not resolve.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Resolve" })).toBeVisible();
  await expect(page.getByText("Incident overview")).toBeVisible();
  await expect(page.getByText("Next step", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/shot-workstation.png" });
});

test("result header offers one next action that navigates", async ({ page }) => {
  await page.goto("/");
  await page
    .getByPlaceholder(/vpn disconnects/i)
    .fill("E2E probe: the FieldRook demo worker is down.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({ timeout: 30000 });

  // A drafted plan (and possibly a pending proposal) makes resolution the
  // single primary action; either way it navigates to the Resolve view.
  await page.getByRole("tab", { name: "Resolve" }).click();
  await page.getByRole("button", { name: "New resolution plan" }).click();
  await page.getByRole("button", { name: "Use demo-worker recovery template" }).click();
  await page.getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  await page.getByRole("tab", { name: "Findings" }).click();
  const next = page.locator(".result-next .button");
  await expect(next).toBeVisible();
  await next.click();
  await expect(page.getByRole("tab", { name: "Resolve" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible();
});
