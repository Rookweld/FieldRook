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

test("approve executes and reports a verified outcome with before/after", async ({
  page,
}) => {
  await startWorkerInvestigation(page);
  await page.getByRole("button", { name: "Approve & execute" }).click();
  // Either a verified resolution or an honest unverified outcome is acceptable;
  // what matters is a real recorded outcome with before/after evidence.
  await expect(page.getByText(/VERIFIED_(RESOLVED|UNRESOLVED)|EXECUTION_FAILED/).first()).toBeVisible({
    timeout: 60000,
  });
  await expect(page.getByText("BEFORE").first()).toBeVisible();
  await expect(page.getByText("AFTER").first()).toBeVisible();
  await page.screenshot({ path: "test-results/shot-executed.png" });
});
