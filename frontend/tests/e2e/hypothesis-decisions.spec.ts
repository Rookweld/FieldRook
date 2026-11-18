import { expect, test } from "@playwright/test";

// UI-only seam: use the REAL isolated backend response, adding an audited
// record that the simulated provider intentionally does not emit. Python
// integration tests separately exercise the real journal production path.
test("M033-G journal distinguishes reported sources from measured proof", async ({ page }) => {
  await page.route("**/api/investigations", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const original = await route.fetch();
    const data = await original.json();
    if (!Array.isArray(data.hypotheses) || data.hypotheses.length === 0) {
      throw new Error("Real simulated backend did not create any hypothesis");
    }
    const hypothesis = data.hypotheses[0];
    data.hypothesis_decisions = [
      {
        decision_id: "decision-ui-smoke",
        round: 2,
        hypothesis_id: hypothesis.hypothesis_id,
        hypothesis_title: hypothesis.title,
        proposed_status: "weakened",
        reason: "A technician comparison suggests a different diagnostic branch.",
        evidence_ids: [],
        measured_evidence_ids: [],
        report_refs: ["report:3"],
        rejected_refs: ["unknown-evidence-ref"],
        link_status: "invalid",
        review_state: "pending_technician",
        provenance_note: "References are not proof. Verify before accepting.",
      },
    ];
    await route.fulfill({ response: original, json: data });
  });

  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(
    "M033-G E2E: the technician reports a remote client error.",
  );
  await page.getByLabel("Affected computer").selectOption("remote");
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();

  await expect(page.getByRole("tab", { name: "Guide" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("tab", { name: "Guide" }).click();
  const journal = page.getByRole("region", { name: "Hypothesis decision evidence review" });
  await expect(journal).toBeVisible();
  await expect(journal.getByRole("heading", { name: "Hypothesis decision journal" })).toBeVisible();
  await expect(journal).toContainText("pending technician");
  await expect(journal).toContainText("report:3");
  await expect(journal).toContainText("unknown-evidence-ref");
  await expect(journal).toContainText("References are not proof");
  await expect(page.getByRole("button", { name: "Record your judgment" }).first()).toBeVisible();
});
