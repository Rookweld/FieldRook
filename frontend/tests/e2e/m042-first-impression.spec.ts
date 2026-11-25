import { expect, test } from "@playwright/test";

test.use({ storageState: { cookies: [], origins: [] }, reducedMotion: "reduce" });

const BROKEN_BRIDGE = [
  "A Windows diagnostic bridge flashes ONLINE then OFFLINE.",
  "The launcher remains open but the tunnel-client and Python MCP processes disappear after startup.",
  "Several failed startup attempts suggest there may be multiple independent blockers.",
  "The technician has not yet inspected PowerShell errors, configuration locations or port bindings.",
].join(" ");

async function startFixtureCase(page: import("@playwright/test").Page, description = BROKEN_BRIDGE) {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" })
    .getByRole("button", { name: "Workbench", exact: true }).click();
  await page.locator("#sf-engine-problem").fill(description);
  await page.getByText("Advanced: fixture mode, provider").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.locator("#sf-case-headline")).toBeVisible({ timeout: 35000 });
}

test("M042 concise headline keeps the complete original problem report", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await startFixtureCase(page);
  await page.screenshot({ path: "test-results/m042-desktop-1600.png" });
  const frame = await page.locator(".sf-next").boundingBox();
  const cta = await page.locator(".sf-next .sf-btn-lime").boundingBox();
  expect(frame).not.toBeNull();
  expect(cta).not.toBeNull();
  expect(cta!.y + cta!.height).toBeLessThanOrEqual(frame!.y + frame!.height - 2);
  const heading = page.locator("#sf-case-headline");
  await expect(heading).toHaveText("A Windows diagnostic bridge flashes ONLINE then OFFLINE.");
  await expect.poll(async () => page.locator("#sf-main").evaluate((el) => el.scrollTop))
    .toBeLessThan(70);
  await expect(page.getByText("Read the full problem report")).toBeVisible();
  await page.getByText("Read the full problem report").click();
  await expect(page.locator(".sf-case-original p")).toHaveText(BROKEN_BRIDGE);
  await expect(page.locator(".sf-hero-details")).toContainText("Fixture evidence");
  const heroHeight = await page.locator(".sf-hero-case").evaluate((el) => el.getBoundingClientRect().height);
  expect(heroHeight).toBeLessThan(390);
});

test("M042 badge reports case inference, not the server default", async ({ page }) => {
  await page.route("**/api/investigations", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const res = await route.fetch();
    const body = await res.json();
    // A real-case schema returned by the backend, with only provider
    // provenance overridden to model the M041 local-Ollama scenario.
    // This is a UI contract test, NOT proof of network inference.
    body.model = "local/qwen3:4b";
    body.analysis_mode = "live";
    body.uses_fixtures = false;
    body.evidence = [];
    await route.fulfill({ response: res, json: body });
  });
  await startFixtureCase(page);
  await expect(page.locator(".sf-topbar [role='status']"))
    .toContainText("Case: Local AI · 0 evidence records");
  await expect(page.locator(".sf-hero-details")).toContainText("Local AI analysis");
  await expect(page.locator(".sf-hero-details")).toContainText("0 evidence records");
  await expect(page.locator(".sf-topbar")).not.toContainText("Simulated analysis");
  await expect(page.locator(".sf-status")).toContainText("case local/qwen3:4b (live)");
});

test("M042 follow-up presents updated analysis at top of workbench", async ({ page }) => {
  await startFixtureCase(page);
  const main = page.locator("#sf-main");
  await page.locator("#followup-input").scrollIntoViewIfNeeded();
  await page.locator("#followup-input").fill(
    "Technician observation: Windows PowerShell 5.1 cannot import Microsoft.PowerShell.Security."
  );
  const scrollBefore = await main.evaluate((el) => el.scrollTop);
  expect(scrollBefore).toBeGreaterThan(80);
  await page.getByRole("button", { name: "Send follow-up", exact: true }).click();
  await expect(page.locator("#followup-input")).toHaveValue("", {timeout:35000});
  await expect.poll(async () => main.evaluate((el) => el.scrollTop), {timeout:5000}).toBeLessThan(60);
  await expect(page.locator("#sf-case-headline")).toBeVisible();
});

test("M042 hero stays compact on narrow screens", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 950 });
  await startFixtureCase(page);
  await expect.poll(async () => page.evaluate(() => window.scrollY)).toBeLessThan(10);
  await page.screenshot({ path: "test-results/m042-mobile-700.png" });
  const hero = page.locator(".sf-hero-case");
  const height = await hero.evaluate((el) => el.getBoundingClientRect().height);
  expect(height).toBeLessThan(420);
  await expect(page.locator("#sf-case-headline")).toBeVisible();
  await expect(page.getByText("Read the full problem report")).toBeVisible();
});
