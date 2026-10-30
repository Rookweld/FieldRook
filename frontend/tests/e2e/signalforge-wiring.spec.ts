import { expect, test } from "@playwright/test";

/**
 * SIGNALFORGE wiring surface (GAMMA). The BETA views do not exist yet, so
 * these specs pin the backend surface every GAMMA hook depends on: status
 * identity, investigation lifecycle reads, export formats, providers,
 * tools, and knowledge reads. Request-level only; no DOM needed.
 */
const BACKEND = "http://127.0.0.1:8123";

test("status carries the desktop-identity fields", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/status`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as Record<string, unknown>;
  expect(body.service).toBe("fieldrook-api");
  expect(typeof body.runtime).toBe("string");
  expect(typeof body.version).toBe("string");
  expect(typeof body.model_mode).toBe("string");
});

test("providers, tools, and knowledge list endpoints answer", async ({ request }) => {
  const providers = await request.get(`${BACKEND}/api/providers`);
  expect(providers.ok()).toBeTruthy();
  const providerList = (await providers.json()) as Array<Record<string, unknown>>;
  expect(providerList.length).toBeGreaterThan(0);
  expect(typeof providerList[0].name).toBe("string");

  const tools = await request.get(`${BACKEND}/api/tools`);
  expect(tools.ok()).toBeTruthy();
  const toolList = (await tools.json()) as Array<Record<string, unknown>>;
  expect(toolList.length).toBeGreaterThan(0);

  const knowledge = await request.get(`${BACKEND}/api/knowledge`);
  expect(knowledge.ok()).toBeTruthy();
  expect(Array.isArray(await knowledge.json())).toBeTruthy();
});

test("investigation create/read/export roundtrip", async ({ request }) => {
  const created = await request.post(`${BACKEND}/api/investigations`, {
    multipart: { problem: "Wiring probe: VPN disconnects every hour", share_consent: "true" },
  });
  expect(created.ok()).toBeTruthy();
  const inv = (await created.json()) as Record<string, unknown>;
  expect(typeof inv.investigation_id).toBe("string");
  expect(Array.isArray(inv.evidence)).toBeTruthy();
  expect(Array.isArray(inv.hypotheses)).toBeTruthy();
  const id = inv.investigation_id as string;

  const read = await request.get(`${BACKEND}/api/investigations/${id}`);
  expect(read.ok()).toBeTruthy();

  const listed = await request.get(`${BACKEND}/api/investigations?limit=50`);
  expect(listed.ok()).toBeTruthy();
  const rows = (await listed.json()) as Array<Record<string, unknown>>;
  expect(rows.some((row) => row.investigation_id === id)).toBeTruthy();

  const jsonExport = await request.get(`${BACKEND}/api/investigations/${id}/export?format=json`);
  expect(jsonExport.ok()).toBeTruthy();
  const exported = (await jsonExport.json()) as Record<string, unknown>;
  expect(exported.investigation_id).toBe(id);

  const mdExport = await request.get(`${BACKEND}/api/investigations/${id}/export?format=markdown`);
  expect(mdExport.ok()).toBeTruthy();
  const text = await mdExport.text();
  expect(text).toContain(id);

  const bogus = await request.get(`${BACKEND}/api/investigations/${id}/export?format=pdf`);
  expect(bogus.status()).toBe(400);
});

test("unknown investigation and knowledge entries 404 honestly", async ({ request }) => {
  const inv = await request.get(`${BACKEND}/api/investigations/does-not-exist`);
  expect(inv.status()).toBe(404);
  const entry = await request.get(`${BACKEND}/api/knowledge/does-not-exist`);
  expect(entry.status()).toBe(404);
});
