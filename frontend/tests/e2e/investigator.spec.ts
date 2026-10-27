import { expect, test } from "@playwright/test";

test("evidence re-check shows unchanged verdict and history", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: DNS does not resolve anything since this morning.",
  );
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });

  // Progress panel with budget and no open re-checks on fresh evidence.
  await expect(page.getByText("Investigation progress")).toBeVisible();
  await expect(page.getByText(/Tool budget:/)).toBeVisible();
  await expect(page.getByText("Unresolved questions")).toBeVisible();

  // Re-check the DNS config card; fixtures return identical readings.
  const dnsCard = page.locator("article.evidence-item", { hasText: "dns_config" }).first();
  await expect(dnsCard).toBeVisible();
  await dnsCard.getByRole("button", { name: "Re-check" }).click();

  await expect(page.getByText("Evidence changes between rounds")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("UNCHANGED", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/HISTORICAL — SUPERSEDED BY/)).toBeVisible();
  // M010-5: superseded JSON collapses to an expandable summary line.
  await expect(page.getByText("Superseded JSON").first()).toBeVisible();
  await expect(page.getByText(/RE-CHECK OF ev-/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /re-check/i })).toBeVisible();
  await page.screenshot({ path: "test-results/shot-reverify.png", fullPage: true });
});

test("network contradiction surfaces with a targeted re-check", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: the network is down on this machine, I am sure the cable is unplugged.",
  );
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });

  await expect(page.getByText("Contradictions (1)")).toBeVisible();
  await expect(page.getByText("Suggested next checks")).toBeVisible();
  await page.getByRole("button", { name: "Re-check now" }).click();
  await expect(page.getByText("UNCHANGED", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  // The contradiction stands on two agreeing readings — reported honestly.
  await expect(page.getByText("Contradictions (1)")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-contradiction.png", fullPage: true });
});
