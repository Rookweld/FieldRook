import { expect, test } from "@playwright/test";

test("M045-D shows a truthful ready state and only reports work while a turn is pending", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "A laptop can connect to a phone hotspot but cannot browse the internet."
  );
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  const focus = page.locator(".guide-focus-only");
  await expect(focus).toBeVisible({ timeout: 35000 });
  const header = focus.locator(".fr-live-header");
  await expect(header).toContainText(/Your answer is needed|Next check is ready|Ready for your update/);
  await expect(header).not.toContainText("Processing your update");

  await page.route("**/api/investigations/*/turn", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1400));
    await route.continue();
  });

  await focus.locator("#turn-input").fill("Windows connects to the hotspot but DNS resolution fails.");
  await focus.getByRole("button", { name: "Send to FieldRook" }).click();
  await expect(header).toContainText("Processing your update", { timeout: 3000 });
  await expect(focus.getByText(/Waiting for the analysis response/)).toBeVisible();
  await expect(header).not.toContainText("Processing your update", { timeout: 35000 });
  await expect(page.getByRole("tab", { name: "Findings" })).toHaveAttribute("aria-selected", "true");
  await page.unroute("**/api/investigations/*/turn");
});