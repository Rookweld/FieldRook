import { expect, test } from "@playwright/test";

test("history lists investigations with export links", async ({ page }) => {
  await page.goto("/");
  const probe = `E2E history probe ${Date.now()}`;
  await page.getByPlaceholder(/vpn disconnects/i).fill(probe);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Diagnostic activity")).toBeVisible({ timeout: 30000 });

  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  const markdown = page.getByRole("link", { name: "Markdown" }).first();
  const json = page.getByRole("link", { name: "JSON" }).first();
  await expect(markdown).toHaveAttribute("href", /export\?format=markdown/);
  await expect(json).toHaveAttribute("href", /export\?format=json/);

  // Reopen the investigation from history.
  await page.getByText(probe).first().click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Diagnostic activity")).toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: "test-results/shot-history.png" });
});
