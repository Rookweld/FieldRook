import { expect, test } from "@playwright/test";

test("evidence links open a compact preview without jumping the page", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: my VPN disconnects every 10 minutes.",
  );
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  const ref = page.locator(".overview .chip-button").first();
  await expect(ref).toBeVisible({ timeout: 30000 });
  const id = (await ref.innerText()).trim();
  await ref.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  await ref.click();
  await expect(page.getByRole("region", { name: `Evidence ${id} quick view` })).toBeVisible();
  await page.waitForTimeout(550);
  const after = await page.evaluate(() => window.scrollY);
  expect(Math.abs(after - before)).toBeLessThanOrEqual(3);
  await expect(page.getByRole("button", { name: "Go to full evidence" })).toBeVisible();
  await page.getByRole("button", { name: "Close evidence preview" }).click();
  await expect(page.getByRole("region", { name: `Evidence ${id} quick view` })).toHaveCount(0);
});
