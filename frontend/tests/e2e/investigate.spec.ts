import { expect, test } from "@playwright/test";

test("fixture network investigation shows activity, evidence, assessment", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: my VPN disconnects every 10 minutes.",
  );
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  // Investigation header with honest mode badges.
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("SIMULATED", { exact: true })).toBeVisible();
  // Timeline with real tool records.
  await expect(page.getByText("Diagnostic activity")).toBeVisible();
  await expect(page.getByText(/get_network_adapters|get_ip_config/).first()).toBeVisible();
  // Evidence cards and assessment with cited facts.
  await expect(page.getByText("ev-1").first()).toBeVisible();
  await expect(page.getByText(/OBSERVED|Observed facts/).first()).toBeVisible();
  // Resolution banner: diagnosed, nothing verified.
  await expect(page.getByText(/UNRESOLVED — diagnosed/i)).toBeVisible();
  await page.screenshot({ path: "test-results/shot-investigation.png" });

  // Follow-up continues the same investigation with a second round.
  await page.getByPlaceholder(/recently disconnected/i).fill("E2E probe: which observation supports that?");
  await page.getByRole("button", { name: "Send follow-up" }).click();
  await expect(page.getByText("Round 2 — follow-up")).toBeVisible({ timeout: 30000 });
});

test("bare task question collects scheduled-tasks evidence (M010-1)", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: is the FieldRookDemoPhantom task safe to disable?",
  );
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("Scheduled tasks").first()).toBeVisible({ timeout: 15000 });
});
