import { expect, test, type Page } from "@playwright/test";

/**
 * FORGE workstation spec (EPSILON). Written against the documented props
 * contract in frontend/src/forge/types.ts. Requires lead wiring:
 * - WorkspaceShell mounted in the App.tsx problem tab (post-investigation)
 * - IntakeCollectorCard beside the screenshot input (intake form)
 * - CollectorImportCard mounted for the active investigation
 * - onAction("import-collector") -> POST .../import-collector (full replace)
 * Runs at integration time after lead wiring; EPSILON iterates if red.
 */

async function investigateFixture(page: Page, problem: string) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(problem);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByTestId("forge-workspace")).toBeVisible({ timeout: 30000 });
}

const HEAD_VIEW: [RegExp, string][] = [
  [/review proposed correction|capture pre-fix baseline|record the intervention|confirm fix|export report|review resolution/i, "Resolve"],
  [/answer clarifying question|work the next step/i, "Guide"],
  [/continue investigation|re-check stale evidence/i, "Findings"],
];

test("intake offers collector package entry with consent gating", async ({ page }) => {
  await page.goto("/");
  const card = page.getByTestId("forge-intake-collector");
  await expect(card).toBeVisible();

  // No file -> honest error, nothing emitted.
  await card.getByRole("button", { name: "Attach package" }).click();
  await expect(card.getByText(/choose a collector package/i)).toBeVisible();

  // Non-zip -> rejected client-side.
  await card.locator('input[type="file"]').setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a zip"),
  });
  await card.getByRole("checkbox").check();
  await card.getByRole("button", { name: "Attach package" }).click();
  await expect(card.getByText(/zip files/i)).toBeVisible();

  // Zip without consent -> consent error.
  await card.locator('input[type="file"]').setInputFiles({
    name: "collector.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("PK\x03\x04dummy"),
  });
  await card.getByRole("checkbox").uncheck();
  await card.getByRole("button", { name: "Attach package" }).click();
  await expect(card.getByText(/sharing consent is required/i)).toBeVisible();
});

test("workspace shell composes happening-now, rail, queue, and dock", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: my VPN disconnects every 10 minutes.");

  const now = page.getByTestId("forge-happening-now");
  await expect(now).toBeVisible();
  await expect(now.getByText("Key observations")).toBeVisible();

  const rail = page.getByTestId("forge-discovered-rail");
  await expect(rail).toBeVisible();
  await expect(page.getByTestId("forge-rail-counts")).toContainText(/usable/);

  const queue = page.getByTestId("forge-next-up");
  await expect(queue).toBeVisible();
  await expect(page.getByTestId("forge-next-run")).toBeVisible();

  await expect(page.getByTestId("forge-respond-dock")).toBeVisible();
  await expect(page.locator("#forge-respond-input")).toBeVisible();
  await expect(page.locator("#forge-note-input")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-forge-workspace.png" });
});

test("discovered rail opens the evidence view", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: DNS does not resolve.");
  await page.getByTestId("forge-discovered-rail").getByRole("button", { name: "Open evidence" }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toHaveAttribute("aria-selected", "true");
});

test("next-up head runs the same navigation as the overview", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: the FieldRook demo worker is down.");
  const run = page.getByTestId("forge-next-run");
  const label = (await run.textContent()) ?? "";
  const target = HEAD_VIEW.find(([re]) => re.test(label))?.[1];
  expect(target, `head label maps to a view: ${label}`).toBeDefined();
  await run.click();
  await expect(page.getByRole("tab", { name: target as string })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("respond dock sends a turn, a follow-up, and saves a note", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: Excel will not open files from Teams.");
  const dock = page.getByTestId("forge-respond-dock");

  // Kind tabs switch the turn kind; observation reports through sendTurn.
  await dock.getByRole("tab", { name: "Test result" }).click();
  await expect(dock.getByRole("tab", { name: "Test result" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.locator("#forge-respond-input").fill("Rebooted; Teams files still fail to open.");
  await dock.getByRole("button", { name: "Send to FieldRook" }).click();
  await expect(page.locator("#forge-respond-input")).toHaveValue("", { timeout: 30000 });

  // Follow-up mode continues the investigation through the followup endpoint.
  await dock.getByRole("button", { name: "Ask follow-up" }).click();
  await page.locator("#forge-respond-input").fill("Which observation supports that?");
  await dock.getByRole("button", { name: "Send follow-up" }).click();
  await expect(page.locator("#forge-respond-input")).toHaveValue("", { timeout: 30000 });

  // Notes persist on the investigation and appear in the dock list.
  await page.locator("#forge-note-input").fill("E2E forge note: user shown the error dialog.");
  await dock.getByRole("button", { name: "Save note" }).click();
  await expect(
    dock.getByText("E2E forge note: user shown the error dialog."),
  ).toBeVisible({ timeout: 15000 });
});

test("collector import validates, then posts FormData to the lead endpoint", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: printer unavailable on the user's laptop.");
  const card = page.getByTestId("forge-collector-import");
  await expect(card).toBeVisible();

  await card.getByRole("button", { name: "Import package" }).click();
  await expect(card.getByText(/choose a collector package/i)).toBeVisible();

  await card.locator('input[type="file"]').setInputFiles({
    name: "collector.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("PK\x03\x04dummy"),
  });
  await card.getByRole("button", { name: "Import package" }).click();
  await expect(card.getByText(/sharing consent is required/i)).toBeVisible();

  // Wired import reaches the lead endpoint as multipart FormData; the
  // backend owns validation from here (422 detail list, no partial ingest).
  await card.getByRole("checkbox").check();
  const requestPromise = page.waitForRequest("**/api/investigations/*/import-collector");
  await card.getByRole("button", { name: "Import package" }).click();
  const request = await requestPromise;
  expect(request.method()).toBe("POST");
  expect(request.headers()["content-type"]).toMatch(/multipart\/form-data/);
});

test.fixme("reference citations render beside evidence when the corpus lands", async ({ page }) => {
  // Requires lead ref endpoints + GAMMA corpus. Intended contract:
  // citations passed to WorkspaceShell render KnowledgeCiteChips with
  // quoted excerpts, display-only, beside the evidence chips.
  await investigateFixture(page, "E2E forge probe: my VPN disconnects every 10 minutes.");
  await expect(page.getByTestId("forge-citations")).toBeVisible();
});
