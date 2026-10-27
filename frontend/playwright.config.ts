import { defineConfig } from "@playwright/test";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const resultsDir = path.join(configDir, "test-results");
const backendDir = path.join(configDir, "..", "backend");
// Prefer the checkout's own venv; fall back to the dev machine's venv.
const localVenv = path.join(backendDir, ".venv", "Scripts", "python.exe");
const devVenv = "C:\\dev\\FieldRook\\backend\\.venv\\Scripts\\python.exe";
const pythonExe = fs.existsSync(localVenv) ? localVenv : devVenv;

// E2E runs the REAL backend (fixture diagnostics, simulated model — no API
// key) and the REAL Vite dev server against an isolated database and demo
// state directory. Nothing touches live services or saved investigations.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir: resultsDir,
  globalTeardown: "./tests/e2e/global-teardown.ts",
  use: {
    baseURL: "http://localhost:4173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // Dedicated port: never collides with a developer's live backend on :8000.
      command: `"${pythonExe}" -m uvicorn app.main:app --host 127.0.0.1 --port 8123`,
      cwd: backendDir,
      url: "http://127.0.0.1:8123/api/status",
      timeout: 60000,
      reuseExistingServer: false,
      env: {
        MODEL_API_KEY: "",
        FIELDROOK_OFFLINE: "1",
        FIELDROOK_FIXTURES: "always",
        FIELDROOK_FIXTURE_WORKER: "failing",
        FIELDROOK_DB_PATH: path.join(resultsDir, "e2e.db"),
        FIELDROOK_DEMO_STATE: path.join(resultsDir, "demo-state"),
      },
    },
    {
      command: "pnpm exec vite --port 4173 --strictPort",
      url: "http://localhost:4173",
      timeout: 90000,
      reuseExistingServer: false,
      env: {
        FIELDROOK_API_PORT: "8123",
      },
    },
  ],
});
