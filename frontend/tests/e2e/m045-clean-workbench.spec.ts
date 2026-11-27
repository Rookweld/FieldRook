import { expect, test } from "@playwright/test";

test("M045-E keeps action visible and reveals case detail only on demand", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "Laptop cannot access the internet using a mobile phone hotspot."
  );
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  await expect(page.locator(".guide-focus-only")).toBeVisible({ timeout: 35000 });
  await expect(page.locator("#turn-input")).toBeVisible();
  await expect(page.locator(".contextbar")).toContainText("CASE WORKSPACE");
  await expect(page.locator(".contextbar")).not.toContainText(
    "Laptop cannot access the internet using a mobile phone hotspot."
  );
  await expect(page.locator(".fr-case-assessment")).not.toHaveAttribute("open");
  await expect(page.locator(".fr-case-utilities")).not.toHaveAttribute("open");
  await expect(page.locator(".fr-case-assessment").getByText("Incident overview")).toBeHidden();

  await page.locator(".fr-case-assessment > summary").click();
  await expect(page.locator(".fr-case-assessment").getByText("Incident overview")).toBeVisible();

  await page.locator(".sf-case-actions").getByRole("button", { name: /Add technician note/ }).click();
  await expect(page.locator(".fr-case-utilities")).toHaveAttribute("open");
  await expect(page.locator("#sf-engine-note")).toBeVisible();
  await expect(page.locator("#sf-engine-note")).toBeFocused();
});
