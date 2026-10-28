import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8123";

async function investigate(page, problem: string, useFixtures = true) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(problem);
  if (useFixtures) {
    await page.getByText("Advanced: fixture mode").click();
    await page.getByText("Force fixture data").click();
  }
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });
}

test("service evidence renders a status module, not plain text", async ({ page, request }) => {
  // Deterministic service_details via API (the UI dropdown needs live data).
  const probe = `M15 service probe ${Date.now()}`;
  const res = await request.post(`${API}/api/investigations`, {
    form: {
      problem: probe,
      service_name: "wuauserv",
      use_fixtures: "true",
      share_consent: "false",
    },
  });
  expect(res.ok()).toBe(true);
  await page.goto("/");
  await page.getByRole("button", { name: "History" }).click();
  await page.getByText(probe).first().click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  const card = page.locator("article.evidence-item", { hasText: "service_details" }).first();
  await expect(card).toBeVisible();
  await expect(card.getByText("STOPPED", { exact: true })).toBeVisible();
  // A stopped Manual service must never read as a fault.
  await expect(card.getByText("STOPPED", { exact: true })).not.toHaveClass(/lvl-error/);
  await expect(card.getByText(/normal idle behavior/)).toBeVisible();
  await expect(card.getByText("Manual", { exact: true })).toBeVisible();
});

test("network evidence renders verdicts and interface groups", async ({ page }) => {
  await investigate(page, "Websites fail to load and Windows reports a DNS server problem.");
  await page.getByRole("tab", { name: /Evidence/ }).click();
  const dns = page.locator("article.evidence-item", { hasText: "dns_test" }).first();
  await expect(dns.getByText("RESOLVES", { exact: true })).toBeVisible();
  await expect(dns.locator("code.net-host")).toHaveText("example.com");
  const cfg = page.locator("article.evidence-item", { hasText: "dns_config" }).first();
  await expect(cfg.locator(".net-iface-name", { hasText: "Wi-Fi" })).toBeVisible();
});

test("crash evidence renders newest-first incident cards", async ({ page }) => {
  await investigate(page, "The application PhotoForge crashes on launch with exception code 0xc0000005.");
  await page.getByRole("tab", { name: /Evidence/ }).click();
  const card = page.locator("article.evidence-item", { hasText: "app_crashes" }).first();
  await expect(card.getByText(/newest first/)).toBeVisible();
  await expect(card.getByText("0xc0000005").first()).toBeVisible();
  await expect(card.locator(".crash-card strong", { hasText: "EXCEL.EXE" })).toBeVisible();
});

test("findings tell the story: observations, unknowns, coverage", async ({ page }) => {
  await investigate(page, "Is the Windows Update service healthy? It shows as stopped in services.msc.");
  await page.getByRole("tab", { name: "Findings" }).click();
  const story = page.locator(".view-panel");
  await expect(story.getByText("Key observations")).toBeVisible();
  await expect(story.getByText("Still unknown")).toBeVisible();
  await expect(page.getByText("Checked —")).toBeVisible();
  // Observation chips open previews without losing context. Settle the
  // scroll position first: the workspace shell above the panel can leave
  // the chip below the fold, and the click's own scroll is not the point.
  const chip = page.locator(".view-panel .story-obs button.chip-button").first();
  await chip.scrollIntoViewIfNeeded();
  const y0 = await page.evaluate(() => window.scrollY);
  await chip.click();
  await expect(page.getByText("Go to full evidence")).toBeVisible();
  const y1 = await page.evaluate(() => window.scrollY);
  expect(Math.abs(y1 - y0)).toBe(0);
  await page.keyboard.press("Escape");
});

test("timeline shows a kind-colored rail with clickable refs", async ({ page }) => {
  await investigate(page, "My VPN disconnects every 10 minutes.");
  await page.getByRole("tab", { name: /Evidence/ }).click();
  const timeline = page.locator("ol.timeline").first();
  await expect(timeline).toBeVisible();
  await expect(timeline.locator(".tl-fam-tool").first()).toBeVisible();
  await expect(timeline.locator(".tl-fam-evidence").first()).toBeVisible();
  await timeline.locator("button.chip-button").first().click();
  await expect(page.getByText("Go to full evidence")).toBeVisible();
  await page.keyboard.press("Escape");
});

test("resolve plans show stages and before/after criteria", async ({ page }) => {
  await investigate(page, "E2E probe: the FieldRook demo worker is down.");
  await page.getByRole("tab", { name: "Resolve" }).click();
  await expect(page.getByRole("heading", { name: /Resolution workspace/ })).toBeVisible();
  await page.getByRole("button", { name: "New resolution plan" }).click();
  await page.getByRole("button", { name: "Use demo-worker recovery template" }).click();
  await page.getByRole("button", { name: "Create resolution plan" }).click();
  await expect(page.getByText("DRAFT", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  const plan = page.locator("article.action-card", { hasText: "Capture pre-fix baseline" }).first();
  for (const stage of ["Plan", "Baseline", "Intervene", "Verify", "Verdict"]) {
    await expect(plan.getByText(stage, { exact: true })).toBeVisible();
  }
  await expect(plan.getByText("UNMEASURED").first()).toBeVisible();
  await expect(plan.getByText("Before", { exact: true }).first()).toBeVisible();
  await expect(plan.getByText("After", { exact: true }).first()).toBeVisible();
});
