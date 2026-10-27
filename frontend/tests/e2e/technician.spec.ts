import { expect, test } from "@playwright/test";

test("presets fill the problem template", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Application problem" }).click();
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toHaveValue(/The application/);
  await page.getByRole("button", { name: "Network problem" }).click();
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toHaveValue(/Network problem/);
  await page.getByRole("button", { name: "Windows \/ background process" }).click();
  await expect(page.getByPlaceholder(/vpn disconnects/i)).toHaveValue(/Windows background problem/);
});

test("crash investigation shows overview, grouped evidence, runbook", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Application problem" }).click();
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "E2E probe: Excel closes when I open a particular workbook.",
  );
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible({ timeout: 30000 });
  // Incident overview with leading hypothesis and coverage.
  await expect(page.getByText("Incident overview")).toBeVisible();
  await expect(page.getByText("Leading hypothesis")).toBeVisible();
  // Grouped evidence: the crash tool ran.
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("search_application_crashes").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /Applications/ })).toBeVisible();
  // Runbook steps with impact badges.
  await page.getByRole("tab", { name: "Findings" }).click();
  await expect(page.getByText("Technician next steps")).toBeVisible();
  await expect(page.getByText("read-only").first()).toBeVisible();
  await page.screenshot({ path: "test-results/shot-technician.png" });
});

test("technician note saves and survives reopen", async ({ page }) => {
  await page.goto("/");
  const probe = `E2E notes probe ${Date.now()}`;
  await page.getByPlaceholder(/vpn disconnects/i).fill(probe);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Diagnostic activity")).toBeVisible({ timeout: 30000 });
  await page.getByRole("tab", { name: "Findings" }).click();

  const noteText = `E2E note ${Date.now()}: user confirmed the dialog text.`;
  await page.getByPlaceholder(/user showed the error dialog/i).fill(noteText);
  await page.getByRole("button", { name: "Save note" }).click();
  const savedNote = page.locator("ul.notes").getByText(noteText);
  await expect(savedNote).toBeVisible({ timeout: 15000 });

  // Reopen from history: the note persisted server-side.
  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByText(probe).first()).toBeVisible({ timeout: 15000 });
  await page.getByText(probe).first().click();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Diagnostic activity")).toBeVisible({ timeout: 15000 });
  await page.getByRole("tab", { name: "Findings" }).click();
  await expect(page.locator("ul.notes").getByText(noteText)).toBeVisible({ timeout: 15000 });
});
