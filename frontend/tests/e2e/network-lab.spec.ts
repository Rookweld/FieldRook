import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// Relative API path: the request fixture inherits baseURL, and Vite proxies
// /api to the (possibly alternate-port) E2E backend. Works under both the
// standard config (:8123/:4173) and alternate-port configs.

async function startCase(
  request: APIRequestContext,
  problem: string,
  target: string,
): Promise<string> {
  const response = await request.post(`/api/investigations`, {
    form: { problem, target, share_consent: "true" },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { investigation_id: string };
  return body.investigation_id;
}

async function openCaseFromLaunchpad(page: Page, problem: string): Promise<void> {
  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("button", { name: "Launchpad", exact: true })
    .click();
  const opener = page.getByRole("button", { name: problem, exact: false }).first();
  await expect(opener).toBeVisible({ timeout: 30000 });
  await opener.click();
  // Opening leaves the launchpad for the workbench with the case mirrored.
  await expect(page.getByRole("button", { name: problem, exact: false })).toHaveCount(0, {
    timeout: 30000,
  });
}

async function gotoNetworkLab(page: Page): Promise<void> {
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("button", { name: "Network Lab", exact: true })
    .click();
  await expect(page.getByTestId("network-lab")).toBeVisible({ timeout: 15000 });
}

test("network lab shows observed records with tool, source, and collection labels", async ({
  page,
  request,
}) => {
  const problem = `E2E netlab observe ${Date.now()}: my VPN connects but the intranet never loads.`;
  await startCase(request, problem, "local");
  await openCaseFromLaunchpad(page, problem);
  await gotoNetworkLab(page);

  const lab = page.getByTestId("network-lab");
  await expect(lab.getByTestId("network-target-banner")).toContainText(/local target/i);
  // Real observed sections from the registered tools, with provenance badges.
  await expect(lab.getByTestId("network-section-net_adapters")).toContainText(
    "get_network_adapters",
  );
  await expect(lab.getByTestId("network-section-dns_config")).toContainText("get_dns_config");
  await expect(lab.getByText("FIXTURE").first()).toBeVisible();
  await expect(lab.getByText(/Last collected:/).first()).toBeVisible();
  // No invented action promises anywhere in the instrument.
  await expect(lab.getByRole("button", { name: /ping|traceroute|port.?scan/i })).toHaveCount(0);
  await expect(lab.getByPlaceholder(/hostname/i)).toHaveCount(0);
});

test("local re-check needs consent, then records a fresh reading", async ({
  page,
  request,
}) => {
  const problem = `E2E netlab recheck ${Date.now()}: DNS does not resolve anything since this morning.`;
  await startCase(request, problem, "local");
  await openCaseFromLaunchpad(page, problem);
  await gotoNetworkLab(page);

  const lab = page.getByTestId("network-lab");
  const consent = lab.getByTestId("network-lab-consent");
  await expect(consent).toBeVisible();
  const recheck = lab.getByTestId(/network-recheck-ev-/).first();
  await expect(recheck).toBeVisible();
  await expect(recheck).toBeDisabled();
  await expect(recheck).toContainText(/needs consent/i);

  const section = lab.getByTestId("network-section-dns_config");
  const before = await section.getByText(/Last collected:/).count();
  expect(before).toBeGreaterThan(0);

  await consent.check();
  await expect(recheck).toBeEnabled();
  await recheck.click();

  // Fresh reading lands as a new record linked to the old one (data-derived,
  // so it survives the engine reseed that follows every case mutation).
  await expect(section.getByText(/Last collected:/)).toHaveCount(before + 1, { timeout: 30000 });
  await expect(section.getByText(/Re-check of ev-/).first()).toBeVisible({ timeout: 30000 });
});

test("cancel drops a slow re-check and says the reading may still land", async ({
  page,
  request,
}) => {
  const problem = `E2E netlab cancel ${Date.now()}: DNS does not resolve anything since this morning.`;
  await startCase(request, problem, "local");
  await openCaseFromLaunchpad(page, problem);
  await gotoNetworkLab(page);

  const lab = page.getByTestId("network-lab");
  await lab.getByTestId("network-lab-consent").check();
  const recheck = lab.getByTestId(/network-recheck-ev-/).first();
  await expect(recheck).toBeEnabled();

  await page.route("**/api/investigations/*/reverify", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await route.continue();
  });
  await recheck.click();
  const cancel = lab.getByTestId("network-lab-cancel");
  await expect(cancel).toBeVisible({ timeout: 5000 });
  await cancel.click();
  await expect(lab.getByTestId("network-lab-notice")).toContainText(/cancelled locally/i, {
    timeout: 10000,
  });
  await page.unroute("**/api/investigations/*/reverify");
});

test("remote target shows observations only with no run controls", async ({
  page,
  request,
}) => {
  const problem = `E2E netlab remote ${Date.now()}: branch office PC cannot reach the intranet.`;
  await startCase(request, problem, "remote");
  await openCaseFromLaunchpad(page, problem);
  await gotoNetworkLab(page);

  const lab = page.getByTestId("network-lab");
  await expect(lab.getByTestId("network-target-banner")).toContainText(/remote target/i);
  await expect(lab.getByTestId("network-lab-consent")).toHaveCount(0);
  await expect(lab.getByTestId(/network-recheck-ev-/)).toHaveCount(0);
  await expect(
    lab.getByRole("button", { name: /re-check|run|test now|scan/i }),
  ).toHaveCount(0);
  await expect(lab).toContainText(/collector/i);
});

test("unknown target shows host-only readings with no run controls", async ({
  page,
  request,
}) => {
  const problem = `E2E netlab unknown ${Date.now()}: something on some PC broke DNS.`;
  await startCase(request, problem, "unknown");
  await openCaseFromLaunchpad(page, problem);
  await gotoNetworkLab(page);

  const lab = page.getByTestId("network-lab");
  await expect(lab.getByTestId("network-target-banner")).toContainText(/unknown target/i);
  await expect(lab.getByTestId("network-lab-consent")).toHaveCount(0);
  await expect(lab.getByTestId(/network-recheck-ev-/)).toHaveCount(0);
});
