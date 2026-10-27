import { execFileSync, execSync } from "node:child_process";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));

// Stops the demo worker the approve test may have spawned. Only the pid
// recorded in the ISOLATED e2e demo-state heartbeat is touched, and only
// after its live command line proves it is the demo worker script.
export default async function globalTeardown(): Promise<void> {
  const heartbeat = path.join(here, "..", "..", "test-results", "demo-state", "heartbeat.json");
  if (!fs.existsSync(heartbeat)) return;
  let pid: unknown = null;
  try {
    pid = JSON.parse(fs.readFileSync(heartbeat, "utf-8")).pid;
  } catch {
    return;
  }
  if (typeof pid !== "number" || !Number.isInteger(pid) || pid <= 0) return;
  let cmdline = "";
  try {
    cmdline = execSync(
      `powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=${pid}').CommandLine"`,
      { encoding: "utf-8", timeout: 15000 },
    ).toLowerCase();
  } catch {
    return;
  }
  if (!cmdline.includes("demo_worker") || !cmdline.includes("worker.py")) return;
  try {
    execFileSync("taskkill", ["/PID", String(pid), "/F"], { timeout: 15000 });
    console.log(`e2e teardown: stopped demo worker pid=${pid}`);
  } catch {
    // Already gone; nothing to do.
  }
}
