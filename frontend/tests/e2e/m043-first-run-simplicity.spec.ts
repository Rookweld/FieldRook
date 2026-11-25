import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce", storageState: { cookies: [], origins: [] } });

async function openWorkbench(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Workbench", exact: true }).click();
  await expect(page.locator("#sf-engine-problem")).toBeVisible();
}

test("M043 first-run start really navigates to a new investigation and persists dismissal", async ({ page }) => {
  // The prior guide deliberately hides from automated agents, so spoof only
  // webdriver for this one browser contract test to exercise the human path.
  await page.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, "webdriver", { configurable: true, get: () => false });
  });
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto("/");
  const guide = page.getByTestId("forge-first-run");
  await expect(guide).toBeVisible();
  await expect(guide.getByRole("heading", { name: "Bring a real Windows problem." })).toBeVisible();
  await expect(guide.locator(".firstrun-steps li")).toHaveCount(3);
  await expect(guide.locator(".firstrun-more")).not.toHaveAttribute("open");
  await page.screenshot({ path: "test-results/m043-welcome-1600.png" });
  await guide.getByRole("button", { name: /Start my first investigation/ }).click();
  await expect(page.locator("#sf-engine-problem")).toBeVisible();
  await expect(guide).toHaveCount(0);
  await expect.poll(async () => page.evaluate(() => localStorage.getItem("fieldrook.first-run.v1"))).toBe("seen");
  await page.reload();
  await expect(guide).toHaveCount(0);
});

test("M043 intake shows reasoning provenance, keeps advanced options optional", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openWorkbench(page);
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/simulated reasoning/i);
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/not necessarily reachable/i);
  await expect(page.getByRole("button", { name: "Investigate", exact: true })).toBeDisabled();
  await expect(page.getByText("More options: screenshot, Windows service or Collector package")).toBeVisible();
  await expect(page.getByLabel("Inference provider")).toBeHidden();
  await page.locator("#sf-engine-problem").fill("My Bluetooth device disappears after Windows wakes from sleep.");
  await expect(page.getByRole("button", { name: "Investigate", exact: true })).toBeEnabled();
  const buttonBox = await page.getByRole("button", { name: "Investigate", exact: true }).boundingBox();
  expect(buttonBox).not.toBeNull();
  expect(buttonBox!.y + buttonBox!.height).toBeLessThan(875);
  await page.screenshot({ path: "test-results/m043-intake-1600.png" });
});

test("M043 one-click local AI selection never claims endpoint is reachable", async ({ page }) => {
  await page.route("**/api/providers", async route => {
    const response = await route.fetch();
    const providers = await response.json();
    const local = providers.find((item: {name:string}) => item.name === "local");
    expect(local).toBeTruthy();
    local.available = true;
    local.reason = "configured for E2E check";
    await route.fulfill({response, json:providers});
  });
  await openWorkbench(page);
  await expect(page.getByRole("button", { name: /Use configured local AI/ })).toBeVisible();
  await page.getByRole("button", { name: /Use configured local AI/ }).click();
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/Local AI selected/);
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/no connection test has run/);
  await page.getByText("Advanced: fixture mode, provider").click();
  await expect(page.getByLabel("Inference provider")).toHaveValue("local");
  await page.getByRole("button", { name: "Use default analysis" }).click();
  await expect(page.getByLabel("Inference provider")).toHaveValue("auto");
});

test("M043 remote target shows no cross-machine diagnostic promise and fixture alert persists", async ({ page }) => {
  await openWorkbench(page);
  await page.getByLabel("Affected computer").selectOption("remote");
  await expect(page.getByText(/will not inspect the other computer/)).toBeVisible();
  await page.getByText("Advanced: fixture mode, provider").click();
  await page.getByText("Force fixture data").click();
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/Example diagnostic data is ON/);
  await page.locator("#sf-engine-problem").fill("VPN stops working on another computer.");
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({timeout:30000});
  await expect(page.locator(".contextbar")).toContainText("OTHER PC");
  await expect(page.locator(".sf-topbar")).toContainText("fixture data");
});

test("M043 screenshots still require explicit consent in collapsed optional section", async ({ page }) => {
  await openWorkbench(page);
  await page.locator("#sf-engine-problem").fill("An error dialog appears every few minutes.");
  await page.getByText("More options: screenshot, Windows service or Collector package").click();
  await page.getByLabel(/Screenshot \(optional/).setInputFiles({
    name: "test-screenshot.png",
    mimeType: "image/png",
    buffer: Buffer.from("not a real image; consent gate should stop the request"),
  });
  await expect(page.getByText(/authorized to share this screenshot/)).toBeVisible();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Sharing consent is required");
  await expect(page.locator("#sf-engine-problem")).toBeVisible();
});

test("M043 default live provider warns that cloud context can be transmitted", async ({ page }) => {
  await page.route("**/api/status", async route => {
    const response = await route.fetch();
    const status = await response.json();
    status.model_mode = "live";
    status.model_name = "cloud-model-for-ui-test";
    await route.fulfill({response, json:status});
  });
  await openWorkbench(page);
  await expect(page.getByLabel("Selected analysis mode")).toContainText(/cloud provider may transmit redacted investigation context/i);
});

test("M043 narrow intake remains usable without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({width:700,height:950});
  await openWorkbench(page);
  await page.locator("#sf-engine-problem").fill("Wireless audio cuts out when the laptop wakes.");
  await expect(page.getByRole("button", {name:"Investigate", exact:true})).toBeEnabled();
  const widths = await page.locator("#sf-main").evaluate(el => ({
    scroll:el.scrollWidth, client:el.clientWidth
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 2);
  await page.getByRole("button", {name:"Investigate", exact:true}).scrollIntoViewIfNeeded();
  await expect(page.getByRole("button", {name:"Investigate", exact:true})).toBeVisible();
  await page.screenshot({path:"test-results/m043-narrow-700.png"});
});
