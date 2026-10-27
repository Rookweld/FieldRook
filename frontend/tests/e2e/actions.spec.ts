import { expect, test } from "@playwright/test";

async function startWorkerInvestigation(page) {
  await page.goto("/");
  await page
    .getByPlaceholder(/vpn disconnects/i)
    .fill("E2E probe: the FieldRook demo worker is down.");
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("recover_demo_worker").first()).toBeVisible({
    timeout: 30000,
  });
}

test("reject leaves the proposal rejected with zero executions", async ({ page }) => {
  await startWorkerInvestigation(page);
  await page.getByRole("button", { name: "Reject action" }).click();
  await expect(page.getByText("REJECTED").first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/NO ACTION — rejected/i)).toBeVisible();
  await expect(page.getByText(/^Execution exe-/)).toHaveCount(0);
  await page.screenshot({ path: "test-results/shot-rejected.png" });
});

test("approve then execute reports a verified outcome with before/after", async ({
  page,
}) => {
  await startWorkerInvestigation(page);
  // Step 1: approval alone authorizes without executing.
  await page.getByRole("button", { name: "Approve action", exact: true }).click();
  await expect(page.getByText("APPROVED", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/nothing has executed yet/i)).toBeVisible();
  await expect(page.getByText(/^Execution exe-/)).toHaveCount(0);
  await page.screenshot({ path: "test-results/shot-approved.png" });
  // Step 2: deliberate execution records a real outcome with before/after.
  await page.getByRole("button", { name: "Execute approved action" }).click();
  // Either a verified resolution or an honest unverified outcome is acceptable;
  // what matters is a real recorded outcome with before/after evidence.
  await expect(
    page.getByText(/VERIFIED_(RESOLVED|UNRESOLVED)|EXECUTION_FAILED/).first(),
  ).toBeVisible({
    timeout: 60000,
  });
  await expect(page.getByText("BEFORE").first()).toBeVisible();
  await expect(page.getByText("AFTER").first()).toBeVisible();
  await expect(page.locator(".result-strip").getByText("Verified outcome")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-executed.png" });
});
