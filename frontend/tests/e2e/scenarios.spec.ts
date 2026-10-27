import { expect, test } from "@playwright/test";

test("scenario A: phantom task finding stays suspicious-but-unverified", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByPlaceholder(/vpn disconnects/i)
    .fill("E2E probe: PowerShell windows keep flashing every five minutes.");
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  const diagnosis = page.locator("section", {
    has: page.getByRole("heading", { name: "Diagnosis", exact: true }),
  });
  await expect(diagnosis.getByText(/matches the reported cadence/)).toBeVisible({
    timeout: 30000,
  });
  // The incident overview surfaces the same leading hypothesis.
  const overview = page.locator("section", {
    has: page.getByRole("heading", { name: "Incident overview", exact: true }),
  });
  await expect(overview.getByText(/matches the reported cadence/)).toBeVisible();
  await expect(
    page.getByText(/FieldRookDemoPhantom.*has window-hiding text/),
  ).toBeVisible();
  await expect(page.getByText(/Suspicious but unverified/)).toBeVisible();
  await expect(page.getByText(/UNRESOLVED — diagnosed/i)).toBeVisible();
  // Diagnosis only: no corrective action exists for scheduled tasks.
  await expect(page.getByText("No corrective action proposed")).toBeVisible();
});

test("scenario C: insufficient evidence reports UNRESOLVED honestly", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByPlaceholder(/vpn disconnects/i)
    .fill("E2E probe: my laptop freezes randomly every afternoon.");
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  await expect(page.getByText(/UNRESOLVED — diagnosed/i)).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByText("No corrective action proposed")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-scenario-c.png" });
});
