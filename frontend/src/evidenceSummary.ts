import type { EvidenceItem } from "./types";

export type SummaryRow = { label: string; value: string };

function str(value: unknown): string | null {
  if (typeof value === "string" && value !== "") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

function obj(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function fmtScalar(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function joinList(value: unknown, max = 4): string | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const parts = value.slice(0, max).map(fmtScalar);
  return value.length > max ? `${parts.join(", ")} (+${value.length - max} more)` : parts.join(", ");
}

/**
 * Readable per-category summary rows for an evidence item. Every branch is
 * defensive: unknown or truncated shapes fall back to the tool summary so
 * the card never shows an empty or misleading preview.
 */
export function summarizeEvidence(item: EvidenceItem): SummaryRow[] {
  const d = item.data;
  const rows: SummaryRow[] = [];
  const push = (label: string, value: string | null) => {
    if (value !== null && value !== "") rows.push({ label, value });
  };

  if (d["_truncated"] === true) {
    push("Result", str(d["summary"]) ?? "Large result, showing a preview.");
    const total = str(d["total_chars"]);
    if (total) push("Full size", `${total} chars (see JSON)`);
    return rows;
  }

  switch (item.category) {
    case "service_status": {
      push("Service", str(d["name"]));
      push("Display name", str(d["display_name"]));
      push("Status", str(d["status"]));
      push("Service type", str(d["service_type"]));
      break;
    }
    case "startup_type": {
      push("Service", str(d["name"]));
      push("Start type", str(d["startup_type"]));
      push("State", str(d["state"]));
      push("Runs as", str(d["start_name"]));
      break;
    }
    case "service_details": {
      const status = obj(d["status"]);
      const startup = obj(d["startup"]);
      push("Service", str(d["name"]) ?? (status ? str(status["name"]) : null));
      push("Status", status ? str(status["status"]) : str(d["status"]));
      push("Start type", startup ? str(startup["startup_type"]) : null);
      push("Runs as", startup ? str(startup["start_name"]) : null);
      const deps = d["dependencies"] ?? d["depends_on"];
      push("Dependencies", joinList(deps));
      break;
    }
    case "service_list": {
      const services = d["services"];
      push("Result", str(d["summary"]));
      if (Array.isArray(services)) {
        const stopped = services.filter((s) => str(obj(s)?.["status"]) === "Stopped");
        push(
          "Not running",
          stopped.length > 0
            ? joinList(stopped.map((s) => str(obj(s)?.["name"]) ?? "?"))
            : "none — all listed services running",
        );
      }
      break;
    }
    case "event_log": {
      push("Result", str(d["summary"]));
      const logs = d["logs"];
      if (Array.isArray(logs)) {
        for (const log of logs.slice(0, 3)) {
          const events = obj(log)?.["events"];
          if (Array.isArray(events)) {
            for (const ev of events.slice(0, 3)) {
              const o = obj(ev);
              if (!o) continue;
              push(
                `Event ${str(o["id"]) ?? "?"}`,
                `${str(o["level"]) ?? ""} ${str(o["provider"]) ?? ""} — ${(str(o["message"]) ?? "").slice(0, 140)}`.trim(),
              );
            }
          }
        }
      }
      break;
    }
    case "app_crashes": {
      push("Result", str(d["summary"]));
      const crashes = d["crashes"];
      if (Array.isArray(crashes)) {
        for (const crash of crashes.slice(0, 3)) {
          const o = obj(crash);
          if (!o) continue;
          const parts = [
            str(o["app_name"]),
            str(o["exception_code"]) ? `exception ${str(o["exception_code"])}` : null,
            str(o["faulting_module"]) ? `in ${str(o["faulting_module"])}` : null,
            str(o["time_created"]),
          ].filter((p): p is string => p !== null && p !== "");
          if (parts.length > 0) push(`Crash ${str(o["id"]) ?? ""}`.trim(), parts.join(" · "));
        }
      }
      break;
    }
    case "process_info": {
      push("Result", str(d["summary"]));
      const service = obj(d["service"]);
      if (service) {
        push(
          "Service process",
          `${str(service["name"]) ?? "?"}: ${str(service["state"]) ?? "?"}${service["pid"] !== null && service["pid"] !== undefined ? ` (pid ${fmtScalar(service["pid"])})` : ""}`,
        );
      }
      const processes = d["processes"];
      if (Array.isArray(processes) && processes.length > 0) {
        push(
          "Processes",
          joinList(
            processes.map((p) => {
              const o = obj(p);
              return `${str(o?.["name"]) ?? "?"}${o?.["memory_mb"] !== undefined ? ` (${fmtScalar(o?.["memory_mb"])} MB)` : ""}`;
            }),
          ),
        );
      }
      break;
    }
    case "os_info": {
      push("OS", str(d["caption"]));
      push("Version", str(d["version"]));
      push("Build", str(d["build_number"]));
      push("Architecture", str(d["os_architecture"]));
      push("Last boot", str(d["last_boot_up_time"]));
      break;
    }
    case "net_adapters": {
      push("Result", str(d["summary"]));
      push("Adapters", joinList(d["adapters"]));
      break;
    }
    case "ip_config": {
      push("Result", str(d["summary"]));
      push("Addresses", joinList(d["addresses"] ?? d["ip_addresses"]));
      break;
    }
    case "dns_config": {
      push("Result", str(d["summary"]));
      const ifaces = d["interfaces"];
      if (Array.isArray(ifaces)) {
        for (const iface of ifaces.slice(0, 4)) {
          const o = obj(iface);
          if (!o) continue;
          push(str(o["interface"]) ?? "Interface", joinList(o["servers"]) ?? "(no servers)");
        }
      }
      break;
    }
    case "dns_test": {
      push("Host", str(d["hostname"]));
      const ok = d["succeeded"];
      push("Resolves", ok === true ? "yes" : ok === false ? "no" : null);
      push("Addresses", joinList(d["addresses"]));
      push("Query time", d["query_ms"] !== undefined && d["query_ms"] !== null ? `${fmtScalar(d["query_ms"])} ms` : null);
      break;
    }
    case "connections": {
      push("Result", str(d["summary"]));
      const conns = d["connections"];
      if (Array.isArray(conns)) {
        push(
          "Sample",
          joinList(
            conns.map((c) => {
              const o = obj(c);
              return `${str(o?.["local"]) ?? "?"} → ${str(o?.["remote"]) ?? "?"}`;
            }),
            3,
          ),
        );
      }
      break;
    }
    case "scheduled_tasks": {
      push("Result", str(d["summary"]));
      const tasks = d["tasks"];
      if (Array.isArray(tasks)) {
        for (const task of tasks.slice(0, 4)) {
          const o = obj(task);
          if (!o) continue;
          push(
            str(o["task_name"]) ?? "Task",
            `${str(o["state"]) ?? "?"}${str(o["author"]) ? ` · by ${str(o["author"])}` : ""}`,
          );
        }
        if (tasks.length > 4) push("More", `${tasks.length - 4} further tasks (see JSON)`);
      }
      break;
    }
    case "demo_worker": {
      push("Worker", str(d["worker_id"]));
      push("Status", str(d["status"]));
      push("Detail", str(d["detail"]));
      push("Heartbeat age", d["heartbeat_age_s"] !== undefined && d["heartbeat_age_s"] !== null ? `${fmtScalar(d["heartbeat_age_s"])}s` : null);
      push("Process verified", d["process_verified"] === true ? "yes" : d["process_verified"] === false ? "no" : null);
      break;
    }
    case "error_code": {
      push("Input", str(d["input"]));
      push("Hex", str(d["hex"]));
      push("Family", str(d["family"]));
      push("Name", str(d["name"]));
      push("Meaning", str(d["description"]));
      push("Note", str(d["note"]));
      break;
    }
    case "screenshot": {
      push("Result", str(d["summary"]) ?? "Screenshot attached to the investigation.");
      break;
    }
    default: {
      push("Result", str(d["summary"]));
      let count = 0;
      for (const [key, value] of Object.entries(d)) {
        if (key === "summary" || key === "warnings" || count >= 5) continue;
        const rendered = fmtScalar(value);
        if (rendered.length > 220) continue;
        push(key.replace(/_/g, " "), rendered);
        count += 1;
      }
    }
  }

  if (rows.length === 0) {
    push("Result", str(d["summary"]) ?? "Collected (see JSON for details).");
  }
  return rows;
}
