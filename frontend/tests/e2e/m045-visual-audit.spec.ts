import { expect, test } from "@playwright/test";

async function openCase(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "Laptop connects to a phone hotspot but websites do not load."
  );
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.locator(".guide-focus-only")).toBeVisible({ timeout: 35000 });
}

for (const size of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "compact", width: 700, height: 900 },
]) {
  test("M045-E visual audit " + size.name, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await openCase(page);
    await expect(page.locator(".fr-live-header")).toBeVisible();
    await expect(page.locator(".fr-case-assessment")).not.toHaveAttribute("open");
    await expect(page.locator(".fr-case-utilities")).not.toHaveAttribute("open");
    await expect(page.locator("#turn-input")).toBeVisible();
    // The same open clarifying question should not appear twice as a plan step.
    await expect(page.locator(".guide-focus-only .guide-current")).toHaveCount(0);
    await page.locator(".guide-focus-only").scrollIntoViewIfNeeded();
    await page.screenshot({ path: "test-results/m045-clean-" + size.name + ".png" });
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width).toBeLessThanOrEqual(size.width + 2);
  });
}
