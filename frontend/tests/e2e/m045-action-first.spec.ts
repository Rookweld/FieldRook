import { expect, test } from "@playwright/test";

test("M045 opens the current action, not another navigation row", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "Technician cannot connect a laptop to a mobile phone hotspot."
  );
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  // Primary action is now inline. Detailed Guide remains one explicit tab away.
  await expect(page.locator(".guide-focus-only")).toBeVisible({ timeout: 35000 });
  await page.getByRole("tab", { name: "Guide" }).click();

  await expect(page.locator("#sf-engine-tab-guide")).toHaveAttribute("aria-selected", "true");
  const primary = page.locator(".fr-guided-primary");
  await expect(primary).toBeVisible();
  await expect(primary).toBeFocused();
  await expect(primary.getByRole("heading", { name: /Questions for you|Recommended next step/ }).first()).toBeVisible();
  await expect(primary.locator("#turn-input")).toBeVisible();
  const position = await primary.evaluate((el) => el.getBoundingClientRect().top);
  const context = await page.locator(".fr-guided-context").evaluate((el) => el.getBoundingClientRect().top);
  expect(position).toBeLessThan(context);
});