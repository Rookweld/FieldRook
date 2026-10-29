import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

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
  // M023: contextual dock — findings owns notes, so the dock shows the composer only.
  await expect(page.locator("#forge-respond-input")).toBeVisible();
  await expect(page.locator("#forge-note-input")).toBeHidden();
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
  // M023: the dock shows notes on the Guide view (findings owns its own card).
  await page.getByRole("tab", { name: "Guide" }).click();
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

test("reference citations render beside evidence when the corpus matches", async ({ page }) => {
  // Lead ref endpoints + GAMMA corpus landed: the DNS probe matches
  // ref-dns-triage, so citations render KnowledgeCiteChips with quoted
  // excerpts, display-only, beside the evidence chips.
  await investigateFixture(page, "E2E forge probe: DNS does not resolve on this workstation.");
  await expect(page.getByTestId("forge-citations")).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: "test-results/shot-forge-citations.png" });
});

test("respond dock shows one twin per view, both on evidence", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: my VPN disconnects every 10 minutes.");
  // Findings: composer only (notes card owns notes).
  await expect(page.locator("#forge-respond-input")).toBeVisible();
  await expect(page.locator("#forge-note-input")).toBeHidden();
  // Guide: notes only (GuidePanel owns the composer).
  await page.getByRole("tab", { name: "Guide" }).click();
  await expect(page.locator("#forge-respond-input")).toBeHidden();
  await expect(page.locator("#forge-note-input")).toBeVisible();
  // Evidence: both (no twins in view).
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.locator("#forge-respond-input")).toBeVisible();
  await expect(page.locator("#forge-note-input")).toBeVisible();
});


test("workspace shell fits a 390px phone without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await investigateFixture(page, "E2E forge probe: my VPN disconnects every 10 minutes.");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("forge-next-up")).toBeVisible();
  await expect(page.getByTestId("forge-next-run")).toBeVisible();
  await page.screenshot({ path: "test-results/shot-forge-mobile.png" });
});

test("imported collector evidence offers no host re-check", async ({ page }) => {
  await investigateFixture(page, "E2E forge probe: DNS does not resolve on this workstation.");
  const card = page.getByTestId("forge-collector-import");
  const sample = new URL("../../../collector/samples/sample_basic.zip", import.meta.url);
  await card.locator('input[type="file"]').setInputFiles({
    name: "sample_basic.zip",
    mimeType: "application/zip",
    buffer: fs.readFileSync(sample),
  });
  await card.getByRole("checkbox").check();
  await card.getByRole("button", { name: "Import package" }).click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  // Imported items carry the recollect hint instead of a Re-check button.
  const gated = page.locator("article", { has: page.getByTestId("recheck-unavailable") });
  await expect(gated.first()).toBeVisible({ timeout: 15000 });
  await expect(gated.getByRole("button", { name: "Re-check", exact: true })).toHaveCount(0);
  await expect(page.getByText(/import a fresh collector package/i).first()).toBeVisible();
});
