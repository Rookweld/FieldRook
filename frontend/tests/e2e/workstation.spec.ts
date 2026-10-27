import { expect, test } from "@playwright/test";

test("workstation opens with brand, stages, and tabs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /fieldrook/i })).toBeVisible();
  await expect(page.getByText("Diagnose. Verify. Resolve.").first()).toBeVisible();
  // Workflow stepper: Investigate active on a fresh page.
  const stepper = page.locator(".stages");
  await expect(stepper.getByText("Investigate", { exact: true })).toBeVisible();
  await expect(stepper.getByText("Understand", { exact: true })).toBeVisible();
  await expect(stepper.getByText("Resolve", { exact: true })).toBeVisible();
  await expect(page.locator(".stage-active", { hasText: "Investigate" })).toBeVisible();
  // Tabs.
  await expect(page.getByRole("button", { name: "Investigate problem" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Service lookup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "History" })).toBeVisible();
  // Intake form.
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Investigate", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/shot-workstation.png" });
});
