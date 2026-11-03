import { expect, test, type Page } from "@playwright/test";

/**
 * FIELD KIT dock (M028.A): open/close/collapse, tool switching, up to 3
 * pinned favorites, and returning to the selected evidence record without
 * losing case state. The dock never remounts the engine, so every test
 * also pins engine continuity (Findings tab + evidence count).
 *
 * Locator note: the dock switcher deliberately uses plain buttons (NOT
 * role="tab") so the engine's Evidence/Findings/Resolve tabs stay the
 * only tab roles on the page for the M026 specs.
 */
test.use({ viewport: { width: 1280, height: 720 } });

const dock = (page: Page) =>
  page.getByRole("complementary", { name: "Field Kit instrument dock" });

async function startCase(page: Page, probe: string): Promise<void> {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(probe);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({ timeout: 30000 });
}

async function evidenceButtons(page: Page) {
  const group = dock(page).getByRole("group", { name: "Case evidence" });
  await expect(group).toBeVisible({ timeout: 15000 });
  return group.getByRole("button");
}

test("dock opens on the Evidence tab with case records, engine intact", async ({ page }) => {
  await startCase(page, `E2E dock probe ${Date.now()}`);
  const rail = dock(page);
  await expect(rail).toBeVisible();
  await expect(rail.getByRole("button", { name: "Evidence", exact: true })).toHaveAttribute(
    "aria-current",
    "true",
  );
  const buttons = await evidenceButtons(page);
  expect(await buttons.count()).toBeGreaterThan(0);
  // Coming-soon tools are listed but tagged honestly, never as usable.
  await expect(
    rail.getByRole("button", { name: "Process Watch, coming soon", exact: true }),
  ).toBeVisible();
  await expect(rail.getByText("SOON").first()).toBeVisible();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
});

test("switching tools and returning keeps the selected evidence and case", async ({ page }) => {
  await startCase(page, `E2E dock switch probe ${Date.now()}`);
  const rail = dock(page);
  const buttons = await evidenceButtons(page);
  const count = await buttons.count();
  expect(count).toBeGreaterThan(0);
  const target = buttons.nth(Math.min(1, count - 1));
  await target.click();
  await expect(target).toHaveAttribute("aria-current", "true");
  const inspectorHeading = (await rail.locator(".sf-inspector h4").innerText()).trim();

  // Switch away: the unavailable card is honest and offers no fake actions.
  await rail.getByRole("button", { name: "Process Watch, coming soon", exact: true }).click();
  const panel = rail.locator(".sf-dock-panel");
  await expect(panel.getByText("COMING SOON")).toBeVisible();
  await expect(panel.getByText(/not implemented in this build/)).toBeVisible();
  await expect(panel.getByRole("button", { name: /run|scan|test|execute|measure/i })).toHaveCount(0);

  // Return: same record selected, same inspector, engine untouched.
  await rail.getByRole("button", { name: "Evidence", exact: true }).click();
  const after = await evidenceButtons(page);
  expect(await after.count()).toBe(count);
  await expect(after.nth(Math.min(1, count - 1))).toHaveAttribute("aria-current", "true");
  await expect(rail.locator(".sf-inspector h4")).toHaveText(inspectorHeading);
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
});

test("collapse and expand preserves selection and focus", async ({ page }) => {
  await startCase(page, `E2E dock collapse probe ${Date.now()}`);
  const rail = dock(page);
  const buttons = await evidenceButtons(page);
  const target = buttons.nth(0);
  await target.click();

  await rail.getByRole("button", { name: "Collapse Field Kit dock" }).click();
  const strip = page.getByTestId("fieldkit-strip");
  await expect(strip).toBeVisible();
  await expect(page.getByRole("button", { name: "Expand Field Kit dock" })).toBeFocused();
  await expect(rail.getByRole("group", { name: "Field Kit instruments" })).toHaveCount(0);

  // A strip tool opens the dock straight onto that instrument.
  await strip.getByRole("button", { name: /Event Decoder/ }).click();
  await expect(rail.locator(".sf-dock-panel").getByText("COMING SOON")).toBeVisible();
  await rail.getByRole("button", { name: "Evidence", exact: true }).click();
  await expect((await evidenceButtons(page)).nth(0)).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
});

test("close and reopen preserves the dock and refocuses the toggle", async ({ page }) => {
  await startCase(page, `E2E dock close probe ${Date.now()}`);
  const rail = dock(page);
  await evidenceButtons(page);
  const toggle = page.getByTestId("fieldkit-toggle");

  await rail.getByRole("button", { name: "Close Field Kit dock" }).click();
  await expect(rail).toBeHidden();
  await expect(toggle).toBeFocused();

  await toggle.click();
  await expect(rail).toBeVisible();
  expect(await (await evidenceButtons(page)).count()).toBeGreaterThan(0);
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
});

test("pins cap at 3 favorites and survive reload", async ({ page }) => {
  await page.goto("/");
  const rail = dock(page);
  await expect(rail).toBeVisible();

  await rail.getByRole("button", { name: "Pin Evidence", exact: true }).click();
  await rail.getByRole("button", { name: "Pin Process Watch", exact: true }).click();
  await rail.getByRole("button", { name: "Pin Event Decoder", exact: true }).click();
  const pinned = page.getByTestId("fieldkit-pinned");
  await expect(pinned.getByRole("button")).toHaveCount(3);
  await expect(rail.getByText("Pinned Event Decoder (3 of 3).")).toBeVisible();
  // Fourth pin is honestly refused: the control disables with a reason.
  const fourth = rail.getByRole("button", { name: "Pin Command Deck", exact: true });
  await expect(fourth).toBeDisabled();
  expect(await fourth.getAttribute("title")).toContain("Pin limit reached");

  await page.reload();
  await expect(page.getByTestId("fieldkit-pinned").getByRole("button")).toHaveCount(3);
  const railAfter = dock(page);
  await railAfter.getByRole("button", { name: "Unpin Evidence", exact: true }).click();
  await expect(page.getByTestId("fieldkit-pinned").getByRole("button")).toHaveCount(2);
  await expect(
    railAfter.getByRole("button", { name: "Pin Command Deck", exact: true }),
  ).toBeEnabled();
});

test("keyboard: arrows move between tools, Enter activates, Escape closes", async ({ page }) => {
  await page.goto("/");
  const rail = dock(page);
  await expect(rail).toBeVisible();
  // Mounting the dock never steals focus (StrictMode-safe effect).
  await expect(page.locator("body")).toBeFocused();
  const evidenceTool = rail.getByRole("button", { name: "Evidence", exact: true });
  await evidenceTool.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    rail.getByRole("button", { name: "Process Watch, coming soon", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(rail.locator(".sf-dock-panel").getByText("COMING SOON")).toBeVisible();
  await page.keyboard.press("ArrowLeft");
  await expect(evidenceTool).toBeFocused();

  // Escape inside the dock closes it and returns focus to the toggle.
  await page.keyboard.press("Escape");
  await expect(rail).toBeHidden();
  await expect(page.getByTestId("fieldkit-toggle")).toBeFocused();
});

test("narrow overlay: toggle and Escape dismiss, focus returns", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.goto("/");
  const rail = dock(page);
  const toggle = page.getByTestId("fieldkit-toggle");
  await expect(rail).toBeVisible();
  await expect(toggle).toBeVisible();

  await toggle.click();
  await expect(rail).toBeHidden();
  await toggle.click();
  await expect(rail).toBeVisible();
  // Overlay semantics: Escape dismisses even from main-column focus.
  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Workbench", exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(rail).toBeHidden();
  await expect(toggle).toBeFocused();
});

test("every coming-soon instrument is clearly unavailable", async ({ page }) => {
  await page.goto("/");
  const rail = dock(page);
  for (const title of ["Process Watch", "Event Decoder", "Command Deck", "Field Notes"]) {
    await rail.getByRole("button", { name: `${title}, coming soon`, exact: true }).click();
    const panel = rail.locator(".sf-dock-panel");
    await expect(panel.getByText("COMING SOON")).toBeVisible();
    await expect(panel.getByText(/not implemented in this build/)).toBeVisible();
    await expect(panel.getByRole("button", { name: "Back to Evidence" })).toBeVisible();
  }
  await rail.locator(".sf-dock-panel").getByRole("button", { name: "Back to Evidence" }).click();
  await expect(rail.getByRole("button", { name: "Evidence", exact: true })).toHaveAttribute(
    "aria-current",
    "true",
  );
});
