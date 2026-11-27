import { expect, test } from "@playwright/test";

test("M045 technician answers the next question directly in the case workspace", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "A technician cannot connect a Windows laptop to a mobile hotspot."
  );
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  const focus = page.locator(".guide-focus-only");
  await expect(focus).toBeVisible({ timeout: 35000 });
  await expect(page.getByRole("tab", { name: "Findings" })).toHaveAttribute("aria-selected", "true");
  await expect(focus.getByRole("heading", { name: "Questions for you" })).toBeVisible();

  const answer = focus.getByRole("textbox", { name: /Answer to:/ }).first();
  await answer.fill("Phone hotspot is on, but the laptop reports no internet.");
  await focus.getByRole("button", { name: "Answer", exact: true }).first().click();
  await expect(focus.locator("#turn-input")).toBeVisible({ timeout: 35000 });
  // Same case, same main view. No tab or route transition needed.
  await expect(page.getByRole("tab", { name: "Findings" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#sf-case-headline")).toBeVisible();
  await expect(page.locator(".fr-deep-findings")).toBeVisible();
});