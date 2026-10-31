/**
 * M028.D (preserved from m028/delta-demo): Network Lab flows pinned to
 * engine/SIGNALFORGE DOM + API contracts. Renamed from network-lab.spec.ts
 * to network-lab-flows.spec.ts at merge to keep both builders' suites.
 */
import { expect, test, type Page } from "@playwright/test";

/**
 * M028.D — Network Lab flows, pinned against the DOM/contracts this branch
 * actually ships (engine Evidence tab network cards, /api/tools catalogue,
 * target isolation on reverify). The M028 Lab instrument re-skins these
 * flows; the merge lead owns selector drift, but every behaviour below must
 * survive: observed-only network readings with tool/source/collected_at,
 * passive-config vs active-test separation, the five-tool allowlist, and
 * the remote-target no-measurement guard.
 */

const BACKEND = "http://127.0.0.1:8123";

async function investigateFixture(page: Page, problem: string) {
  await page.goto("/");
  await page.getByPlaceholder(/vpn disconnects/i).fill(problem);
  await page.getByText("Advanced: fixture mode").click();
  await page.getByText("Force fixture data").click();
  await page.getByRole("button", { name: "Investigate", exact: true }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible({ timeout: 30000 });
}

test("lab shows observed adapters, addresses, and DNS config with provenance", async ({
  page,
}) => {
  await investigateFixture(page, "E2E lab probe: my VPN disconnects every 10 minutes.");

  // Fixture provenance is labeled on the case itself.
  await expect(page.getByText("FIXTURES", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByRole("heading", { name: /Network \(3\)/ })).toBeVisible();

  // Measured adapter state, not a generic "network down" claim.
  const adapters = page.locator("#evcard-ev-1");
  await expect(adapters.getByText("Adapters (2)")).toBeVisible();
  await expect(adapters.getByText("Wi-Fi").first()).toBeVisible();
  await expect(adapters.getByText("Up").first()).toBeVisible();
  await expect(adapters.getByText("tool:get_network_adapters:fixture")).toBeVisible();

  // Measured addresses with interface + family.
  const addresses = page.locator("#evcard-ev-2");
  await expect(addresses.getByText("192.168.1.20/24")).toBeVisible();
  await expect(addresses.getByText("IPv4").first()).toBeVisible();
  await expect(addresses.getByText("tool:get_ip_config:fixture")).toBeVisible();

  // Observed DNS servers per interface.
  const dns = page.locator("#evcard-ev-3");
  await expect(dns.getByText("192.168.1.1").first()).toBeVisible();
  await expect(dns.getByText("1.1.1.1").first()).toBeVisible();
  await expect(dns.getByText("tool:get_dns_config:fixture")).toBeVisible();

  // No invented scanners: the lab offers re-checks, never ping/traceroute UI.
  const panel = page.locator(".view-panel");
  await expect(panel.getByRole("button", { name: /ping|traceroute|port.scan/i })).toHaveCount(0);
  await expect(adapters.getByRole("button", { name: "Re-check", exact: true })).toBeVisible();
});

test("lab separates passive DNS config from the active resolution test", async ({
  page,
}) => {
  await investigateFixture(page, "E2E lab probe: intranet hostnames do not resolve.");
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByRole("heading", { name: /Network \(2\)/ })).toBeVisible();

  // Passive observation: configured servers.
  const config = page.locator("#evcard-ev-1");
  await expect(config.getByText("dns_config", { exact: true })).toBeVisible();
  // Exact: the Raw JSON <pre> in the same card repeats the summary string.
  await expect(config.getByText("DNS servers for 2 interfaces (fixture).", { exact: true })).toBeVisible();

  // Active test: one bounded query with its own verdict rendering.
  const dnsTest = page.locator("#evcard-ev-2");
  await expect(dnsTest.getByText("dns_test", { exact: true })).toBeVisible();
  await expect(dnsTest.getByText("example.com").first()).toBeVisible();
  // Exact: the Raw JSON <pre> in the same card contains "resolves to".
  await expect(dnsTest.getByText("RESOLVES", { exact: true })).toBeVisible();
  await expect(dnsTest.getByText("93.184.216.34").first()).toBeVisible();
  await expect(dnsTest.getByText("Query time")).toBeVisible();
  await expect(dnsTest.getByText("tool:test_dns_resolution:fixture")).toBeVisible();

  // The active test is re-runnable and deterministically unchanged.
  // (Scoped + exact: the timeline echoes "Re-check of ev-2 …" as prose.)
  await dnsTest.getByRole("button", { name: "Re-check", exact: true }).click();
  const freshDns = page.locator("#evcard-ev-3");
  await expect(freshDns.getByText("RE-CHECK OF ev-2", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("UNCHANGED", { exact: true }).first()).toBeVisible();
});

test("lab tool catalogue pins the five registered network tools", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/tools`);
  expect(res.ok()).toBeTruthy();
  const tools = (await res.json()) as Array<{ name: string; category: string; family?: string | null }>;
  const network = tools.filter((t) => t.family === "networking");
  expect(network.map((t) => `${t.name}/${t.category}`).sort()).toEqual(
    [
      "get_connections/connections",
      "get_dns_config/dns_config",
      "get_ip_config/ip_config",
      "get_network_adapters/net_adapters",
      "test_dns_resolution/dns_test",
    ].sort(),
  );
  // The allowlist has no ping, traceroute, or port scanner under any name.
  for (const tool of tools) {
    expect(tool.name).not.toMatch(/ping|traceroute|scan/i);
  }
});

test("lab withholds host re-measurement on a remote-target case", async ({
  page,
  request,
}) => {
  await investigateFixture(page, "E2E lab probe: the branch office network is down.");
  // Non-exact: an open-questions dot extends the tab's accessible name.
  await page.getByRole("tab", { name: "Guide" }).click();
  await page.getByLabel("Diagnostic target").selectOption("remote");
  await expect(page.getByText("OTHER PC", { exact: true })).toBeVisible();
  await expect(page.getByText(/host readings are withheld/i)).toBeVisible();

  // Evidence cards drop their Re-check controls and say why.
  await page.getByRole("tab", { name: /Evidence/ }).click();
  const gated = page.locator("article", { has: page.getByTestId("recheck-unavailable") });
  await expect(gated.first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/this case targets remote/).first()).toBeVisible();
  await expect(
    page.locator(".view-panel").getByRole("button", { name: "Re-check", exact: true }),
  ).toHaveCount(0);

  // The API boundary enforces the same guard (409, not a wrong-machine reading).
  const created = await request.post(`${BACKEND}/api/investigations`, {
    multipart: {
      problem: "Lab guard probe: the network is down on this machine.",
      use_fixtures: "true",
      share_consent: "true",
      target: "local",
    },
  });
  expect(created.ok()).toBeTruthy();
  const inv = (await created.json()) as { investigation_id: string };
  const switched = await request.post(`${BACKEND}/api/investigations/${inv.investigation_id}/target`, {
    data: { target: "remote" },
  });
  expect(switched.ok()).toBeTruthy();
  const denied = await request.post(
    `${BACKEND}/api/investigations/${inv.investigation_id}/reverify`,
    { data: { evidence_id: "ev-1" } },
  );
  expect(denied.status()).toBe(409);
  expect(await denied.text()).toContain("Collect on the affected machine instead.");
});
