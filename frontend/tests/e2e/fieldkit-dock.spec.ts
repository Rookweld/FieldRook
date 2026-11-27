import { expect, test, type Page } from "@playwright/test";

/**
 * M046: the operator dock contains only actually available instruments.
 * The inactive/collapsed state is intentional and must remain reversible,
 * keyboard accessible, and independent from case data.
 */
test.use({ viewport: { width: 1280, height: 720 } });

const dock = (page: Page) =>
  page.getByRole("complementary", { name: "Field Kit instrument dock" });

async function expandDock(page: Page) {
  // On narrow layouts the dock may start fully hidden, not just collapsed.
  // Opening it is a separate, intentional interaction.
  if (!(await dock(page).isVisible())) {
    const toggle = page.getByTestId("fieldkit-toggle");
    await expect(toggle).toBeVisible();
    await toggle.click();
  }
  await expect(dock(page)).toBeVisible();
  const expand = dock(page).getByRole("button", { name: "Expand Field Kit dock" });
  if (await expand.isVisible()) await expand.click();
  await expect(dock(page).getByRole("group", { name: "Field Kit instruments" })).toBeVisible();
}

async function openFixtureCase(page: Page) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill("Laptop loses internet over a phone hotspot.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible({ timeout: 30000 });
  await expandDock(page);
}

test("M046 default compact dock can be expanded without opening another view", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem("fieldrook.dock.visibility.v1");
  });
  await page.goto("/");
  await expect(page.getByTestId("fieldkit-strip")).toBeVisible();
  await expandDock(page);
  await expect(dock(page).getByRole("group", { name: "Field Kit instruments" }).getByRole("button", { name: "Evidence", exact: true })).toHaveAttribute("aria-current", "true");
});

test("M046 shows only ready instruments, not feature promises", async ({ page }) => {
  await page.goto("/");
  await expandDock(page);
  const instruments = dock(page).getByRole("group", { name: "Field Kit instruments" });
  await expect(instruments.getByRole("button", { name: "Evidence", exact: true })).toBeVisible();
  for (const name of ["Process Watch", "Event Decoder", "Command Deck", "Field Notes"]) {
    await expect(instruments.getByRole("button", { name: new RegExp(name) })).toHaveCount(0);
  }
  await expect(instruments.getByRole("button")).toHaveCount(2); // Evidence + its Pin control
});

test("M046 selected case evidence survives collapse and reopen", async ({ page }) => {
  await openFixtureCase(page);
  const records = dock(page).getByRole("group", { name: "Case evidence" }).getByRole("button");
  await expect(records.first()).toBeVisible();
  await records.first().click();
  await expect(records.first()).toHaveAttribute("aria-current", "true");
  await dock(page).getByRole("button", { name: "Collapse Field Kit dock" }).click();
  await expect(page.getByTestId("fieldkit-strip")).toBeVisible();
  await page.getByTestId("fieldkit-strip").getByRole("button", { name: "Evidence", exact: true }).click();
  await expect(records.first()).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("tab", { name: "Findings" })).toHaveAttribute("aria-selected", "true");
});

test("M046 close and reopen leave the case and evidence intact", async ({ page }) => {
  await openFixtureCase(page);
  await expect(dock(page).getByRole("group", { name: "Case evidence" })).toBeVisible();
  await dock(page).getByRole("button", { name: "Close Field Kit dock" }).click();
  await expect(dock(page)).toBeHidden();
  const toggle = page.getByTestId("fieldkit-toggle");
  await expect(toggle).toBeFocused();
  await toggle.click();
  await expandDock(page);
  await expect(dock(page).getByRole("group", { name: "Case evidence" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
});

test("M046 Evidence pin survives reload and can be removed", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.removeItem("fieldrook.dock.v1"));
  await page.reload();
  await expandDock(page);
  await dock(page).getByRole("button", { name: "Pin Evidence", exact: true }).click();
  await expect(dock(page).getByRole("button", { name: "Unpin Evidence", exact: true })).toBeVisible();
  await page.reload();
  await expandDock(page);
  await expect(dock(page).getByRole("button", { name: "Unpin Evidence", exact: true })).toBeVisible();
  await dock(page).getByRole("button", { name: "Unpin Evidence", exact: true }).click();
  await expect(dock(page).getByRole("button", { name: "Pin Evidence", exact: true })).toBeVisible();
});

test("M046 obsolete instrument preferences cannot expose unfinished tools", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("fieldrook.dock.v1", JSON.stringify({
      activeId: "process-watch", pins: ["process-watch", "evidence", "event-decoder"]
    }));
  });
  await page.goto("/");
  await expandDock(page);
  await expect(dock(page).getByRole("group", { name: "Field Kit instruments" }).getByRole("button", { name: "Evidence", exact: true })).toHaveAttribute("aria-current", "true");
  await expect(dock(page).getByRole("button", { name: "Unpin Evidence", exact: true })).toBeVisible();
  await expect(dock(page).getByRole("button", { name: /Process Watch|Event Decoder/ })).toHaveCount(0);
});

test("M046 Escape closes the dock and returns focus to its toggle", async ({ page }) => {
  await page.goto("/");
  await expandDock(page);
  const evidence = dock(page).getByRole("button", { name: "Evidence", exact: true });
  await evidence.focus();
  await page.keyboard.press("ArrowRight");
  await expect(evidence).toBeFocused(); // one ready instrument, so navigation wraps
  await page.keyboard.press("Escape");
  await expect(dock(page)).toBeHidden();
  await expect(page.getByTestId("fieldkit-toggle")).toBeFocused();
});

test("M046 narrow layout preserves overlay close and reopen", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.goto("/");
  await expandDock(page);
  const toggle = page.getByTestId("fieldkit-toggle");
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(dock(page)).toBeHidden();
  await toggle.click();
  await expect(dock(page)).toBeVisible();
  await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Workbench", exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(dock(page)).toBeHidden();
  await expect(toggle).toBeFocused();
});
