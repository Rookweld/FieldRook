/* Optional local-only browser smoke; requires Playwright or PLAYWRIGHT_MODULE. */
"use strict";
const fs = require("fs");
const path = require("path");
const http = require("http");
const assert = require("node:assert/strict");
let chromium;
try { ({ chromium } = require("@playwright/test")); }
catch {
  if (!process.env.PLAYWRIGHT_MODULE) throw Error("Install @playwright/test or set PLAYWRIGHT_MODULE");
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE));
}
const ROOT = path.resolve(__dirname, "../../docs/evidence-trials");
const PREVIEW = path.resolve(__dirname, "../../.evidence-browser-qa");
const MIMES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
fs.mkdirSync(PREVIEW, { recursive: true });
const server = http.createServer((request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const file = path.resolve(ROOT, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!file.startsWith(ROOT + path.sep) && file !== ROOT) { response.writeHead(403); response.end(); return; }
    const data = fs.readFileSync(file);
    response.writeHead(200, { "Content-Type": MIMES[path.extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
    response.end(data);
  } catch { response.writeHead(404); response.end("Not found"); }
});
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = "http://127.0.0.1:" + server.address().port + "/";
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe", args: ["--no-sandbox"] });
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    page.on("pageerror", e => errors.push(e.message));
    const res = await page.goto(address, { waitUntil: "networkidle" });
    assert.equal(res.status(), 200);
    await page.locator("#workbench:visible").waitFor({ timeout: 15000 });
    assert.equal((await page.locator("#metric-evaluated").textContent()).trim(), "37/37");
    assert.equal(await page.locator(".case-choice").count(), 3);
    assert.match(await page.locator("#case-title").textContent(), /Five-Minute Phantom/);
    assert.match(await page.locator("#case-verdict").textContent(), /CAUSE NOT VERIFIED/);
    await page.screenshot({ path: path.join(PREVIEW, "desktop.png"), fullPage: true });
    await page.locator(".case-choice").nth(1).click();
    await page.locator("#tab-verification").click();
    assert.match(await page.locator(".result-tag").textContent(), /VERIFIED_RESOLVED/);
    assert.equal(await page.locator(".criterion .passed").count(), 2);
    await page.locator(".case-choice").nth(2).click();
    await page.locator("#tab-verification").click();
    assert.match(await page.locator(".result-tag").textContent(), /NOT_RESOLVED/);
    assert.equal(await page.locator(".criterion .failed").count(), 1);
    await page.locator(".ref-button").first().click();
    assert.equal(await page.locator("#view-content .evidence-detail").count(), 1);
    await page.locator(".case-choice").first().click();
    await page.locator("#tab-reasoning").click();
    assert.ok((await page.locator(".claim").count()) >= 2);
    const overflowDesktop = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
    assert(!overflowDesktop, "Desktop horizontal overflow");
    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    mobile.on("pageerror", e => errors.push(e.message));
    await mobile.goto(address, { waitUntil: "networkidle" });
    await mobile.locator("#workbench:visible").waitFor({ timeout: 15000 });
    await mobile.screenshot({ path: path.join(PREVIEW, "mobile.png"), fullPage: true });
    await mobile.locator(".case-choice").nth(1).click();
    await mobile.locator("#tab-verification").click();
    assert.match(await mobile.locator(".result-tag").textContent(), /VERIFIED_RESOLVED/);
    const overflowMobile = await mobile.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
    assert(!overflowMobile, "Mobile horizontal overflow");
    assert.deepEqual(errors, [], "No browser JS exceptions");
    console.log("BROWSER_SMOKE_PASS: 3 cases, 4 views, citation navigation, verified/failed controls, desktop/mobile, zero JS exceptions or overflow");
    console.log("Screenshots:", PREVIEW);
  } finally { await browser.close(); }
})().catch(err => { console.error("BROWSER_SMOKE_FAIL", err); process.exitCode=1; }).finally(() => server.close());
