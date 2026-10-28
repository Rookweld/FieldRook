import { expect, test } from "@playwright/test";

test("remembered incident matches a later similar investigation", async ({ page }) => {
  const probe = `E2E memory probe ${Date.now()}`;
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(`${probe}: the demo worker is down.`);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("Worked before")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("No similar incidents remembered")).toBeVisible();

  await page.getByRole("button", { name: "Save to knowledge" }).click();
  await expect(page.getByText(/Saved as know-/)).toBeVisible({ timeout: 15000 });

  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  await page.getByText(probe).first().click();
  const card = page.locator("li.recheck", { hasText: probe });
  await expect(card.getByText("UNRESOLVED", { exact: true })).toBeVisible({ timeout: 15000 });

  // A fresh incident with the same symptoms finds the remembered one.
  await page.getByRole("button", { name: "Investigate problem" }).click();
  await page.getByPlaceholder(/vpn disconnects/i).fill(`${probe}: the demo worker is down.`);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("Worked before")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("Why it matched:")).toBeVisible({ timeout: 15000 });

  // "Investigate this hypothesis" runs read-only diagnostics, nothing else.
  await page.getByRole("button", { name: "Investigate this hypothesis" }).first().click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Follow-up received").first()).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: "test-results/shot-memory.png", fullPage: true });
});

test("knowledge entries can be searched and deleted", async ({ page }) => {
  const probe = `E2E forget probe ${Date.now()}`;
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(`${probe}: the demo worker is down.`);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("Worked before")).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Save to knowledge" }).click();
  await expect(page.getByText(/Saved as know-/)).toBeVisible({ timeout: 15000 });

  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await page.getByPlaceholder(/Search problems/).fill(probe);
  await expect(page.getByText(probe)).toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: "test-results/shot-library.png" });
  const card = page.locator("li.recheck", { hasText: probe });
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText(probe)).toHaveCount(0, { timeout: 15000 });
});
