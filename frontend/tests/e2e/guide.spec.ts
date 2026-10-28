import { expect, test } from "@playwright/test";

async function investigateRemote(page, problem: string) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(problem);
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Guide" })).toBeVisible({ timeout: 30000 });
}

test("guided remote investigation answers questions and works the plan", async ({ page }) => {
  await investigateRemote(page, "E2E guide probe: Excel will not open files from Teams.");
  await expect(page.getByText("OTHER PC", { exact: true })).toBeVisible();
  // Assistant strip on Findings points at the Guide.
  await expect(page.getByLabel("Assistant summary")).toBeVisible();
  await page.getByRole("tab", { name: "Guide" }).click();

  // Answer the first clarifying question inline.
  await expect(page.getByText("Questions for you")).toBeVisible();
  const answerBox = page.getByPlaceholder("Type your answer…").first();
  await answerBox.fill("The user's laptop in room 3.");
  await page.getByRole("button", { name: "Answer", exact: true }).first().click();
  // Answered questions collapse into the history record; expand it to verify.
  const history = page.getByText(/Earlier questions/);
  await expect(history).toBeVisible({ timeout: 30000 });
  await history.click();
  await expect(page.getByText("The user's laptop in room 3.")).toBeVisible({ timeout: 30000 });

  // Report an observation through the turn composer.
  await page.locator("#turn-input").fill("Local files open fine; only Teams files fail.");
  await page.getByRole("button", { name: "Send to FieldRook" }).click();
  await expect(page.getByText("Recommended next step")).toBeVisible({ timeout: 30000 });

  // Record an outcome on the current plan step.
  await page.getByRole("button", { name: "Record outcome" }).first().click();
  await page.getByPlaceholder("What did you observe?").fill("Checked on site: Teams sign-in works.");
  await page.getByRole("button", { name: "Save outcome" }).click();
  await expect(page.getByText("Teams sign-in works.")).toBeVisible();

  // The observation is labeled technician-reported evidence.
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByText("Technician reports").first()).toBeVisible();
  await expect(page.getByText("TECHNICIAN-REPORTED").first()).toBeVisible();
  await page.screenshot({ path: "test-results/shot-guide.png" });
});

test("hypothesis judgment and blocked flow stay honest", async ({ page }) => {
  await investigateRemote(page, "E2E guide probe: printer unavailable on the user's laptop.");
  await page.getByRole("tab", { name: "Guide" }).click();
  await expect(page.getByRole("heading", { name: "Hypotheses" })).toBeVisible();

  // Rule out the first hypothesis with a recorded reason.
  await page.getByRole("button", { name: "Record your judgment" }).first().click();
  await page.getByPlaceholder("Why? (recorded in history)").fill("Printer confirmed working on site.");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("RULED OUT").first()).toBeVisible();

  // Marking every step impossible converges to an honest BLOCKED state.
  for (let i = 0; i < 10; i++) {
    if (await page.getByText("Blocked", { exact: true }).isVisible()) break;
    const impossible = page.getByRole("button", { name: "Can't do this" }).first();
    if (!(await impossible.isVisible())) break;
    await impossible.click();
    await page.getByPlaceholder("Why is this step not possible?").fill("No access to that machine.");
    await page.getByRole("button", { name: "Mark impossible" }).click();
    await expect(page.getByText("No access to that machine.").first()).toBeVisible();
  }
  await expect(page.getByText("Blocked", { exact: true })).toBeVisible();
  await expect(page.getByText("No access to that machine.").first()).toBeVisible();
});

test("provider and target switchers update the investigation", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill("E2E guide probe: my VPN disconnects every 10 minutes.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Guide" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("THIS PC", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Guide" }).click();

  await page.getByLabel("Inference provider").selectOption("local");
  await expect(page.getByText("processed on this computer")).toBeVisible();

  await page.getByLabel("Diagnostic target").selectOption("remote");
  await expect(page.getByText("OTHER PC", { exact: true })).toBeVisible();
  await expect(page.getByText(/wrong computer/)).toBeVisible();
});

test("local connection test reports endpoint state honestly", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill("E2E guide probe: local provider visibility.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Guide" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("tab", { name: "Guide" }).click();

  // The E2E backend has no local model configured: profile panel + honest failure.
  await page.getByLabel("Inference provider").selectOption("local");
  await expect(page.getByText("processed on this computer")).toBeVisible();
  await page.getByRole("button", { name: "Test local connection" }).click();
  const result = page.getByTestId("local-test-result");
  await expect(result).toBeVisible({ timeout: 30000 });
  await expect(result).toContainText(/not reachable|not set|refused|no connection/i);
});

test("turn shows elapsed time and offers cancellation", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill("E2E guide probe: cancel path for a slow round.");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Guide" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("tab", { name: "Guide" }).click();

  // Hold the turn response so the in-flight UI is observable.
  await page.route("**/api/investigations/*/turn", async (route) => {
    await new Promise((r) => setTimeout(r, 2500));
    await route.continue();
  });
  await page.locator("#turn-input").fill("Still failing after a reboot.");
  await page.getByRole("button", { name: "Send to FieldRook" }).click();
  await expect(page.getByRole("button", { name: "Cancel this round" })).toBeVisible();
  await expect(page.getByText(/elapsed \ds/i)).toBeVisible();
  await page.getByRole("button", { name: "Cancel this round" }).click();
  // The button flips only after the cancel endpoint accepts the request.
  await expect(page.getByRole("button", { name: "Cancellation requested" })).toBeVisible();
  await expect(page.getByText("Recommended next step")).toBeVisible({ timeout: 30000 });
  await page.unroute("**/api/investigations/*/turn");
});
