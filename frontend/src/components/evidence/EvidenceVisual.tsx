import type { EvidenceItem } from "../../types";
import { CrashVisual } from "./CrashVisual";
import { EventLogVisual } from "./EventLogVisual";
import { NetworkVisual } from "./NetworkVisual";
import { GenericVisual, OpsVisual } from "./OpsVisual";
import { ServiceVisual } from "./ServiceVisual";
import { arr, obj, str } from "./shared";

/** Category → purpose-built renderer. Unknown shapes fall back cleanly. */
export function EvidenceVisual({ item }: { item: EvidenceItem }) {
  switch (item.category) {
    case "service_status":
    case "startup_type":
    case "service_details":
    case "service_list":
      return <ServiceVisual item={item} />;
    case "net_adapters":
    case "ip_config":
    case "dns_config":
    case "dns_test":
    case "connections":
      return <NetworkVisual item={item} />;
    case "app_crashes":
      return <CrashVisual item={item} />;
    case "event_log":
      return <EventLogVisual item={item} />;
    case "process_info":
    case "scheduled_tasks":
    case "demo_worker":
    case "error_code":
      return <OpsVisual item={item} />;
    default:
      return <GenericVisual item={item} />;
  }
}

const CATEGORY_NOUN: Record<string, string> = {
  service_status: "Service",
  startup_type: "Service",
  service_details: "Service",
  service_list: "Services",
  event_log: "Events",
  app_crashes: "Crash",
  process_info: "Process",
  os_info: "System",
  net_adapters: "Network",
  ip_config: "Network",
  dns_config: "DNS",
  dns_test: "DNS",
  connections: "Network",
  scheduled_tasks: "Task",
  demo_worker: "Worker",
  error_code: "Code",
  screenshot: "Shot",
};

/**
 * One honest line per evidence item for the story module. Every branch
 * is defensive and falls back to the summary or category noun.
 */
export function headlineEvidence(item: EvidenceItem): { noun: string; text: string } {
  const noun = CATEGORY_NOUN[item.category] ?? "Evidence";
  const d = item.data;
  if (item.error) return { noun, text: `collection failed: ${item.error.slice(0, 90)}` };
  switch (item.category) {
    case "service_status":
    case "startup_type":
    case "service_details": {
      const name = str(d["name"]) ?? str(obj(d["status"])?.["name"]) ?? "service";
      const state = str(obj(d["status"])?.["status"]) ?? str(d["status"]) ?? str(d["state"]);
      const start = str(obj(d["startup"])?.["startup_type"]) ?? str(d["startup_type"]);
      const parts = [name, state, start].filter((p): p is string => !!p);
      return { noun, text: parts.join(" · ") || str(d["summary"]) || "service reading" };
    }
    case "service_list": {
      const services = arr(d["services"]);
      const stopped = services.filter((s) => str(obj(s)?.["status"]) === "Stopped").length;
      return {
        noun,
        text:
          stopped > 0
            ? `${services.length} listed · ${stopped} stopped`
            : `${services.length} listed · all running`,
      };
    }
    case "dns_test": {
      const host = str(d["hostname"]) ?? "host";
      const ok = d["succeeded"];
      const first = str(arr(d["addresses"])[0]);
      if (ok === true) return { noun, text: `${host} resolves${first ? ` → ${first}` : ""}` };
      if (ok === false) return { noun, text: `${host} does not resolve` };
      return { noun, text: `${host} (result unknown)` };
    }
    case "dns_config": {
      const n = arr(d["interfaces"]).length;
      return { noun, text: n > 0 ? `name servers on ${n} interface${n === 1 ? "" : "s"}` : "no interface data" };
    }
    case "app_crashes": {
      const crashes = arr(d["crashes"]);
      if (crashes.length === 0) return { noun, text: "no crash records matched" };
      const first = obj(crashes[0]);
      const app = str(first?.["app_name"]) ?? "app";
      const code = str(first?.["exception_code"]);
      return { noun, text: `${crashes.length} record${crashes.length === 1 ? "" : "s"} · ${app}${code ? ` ${code}` : ""}` };
    }
    case "event_log": {
      const matched = str(d["matched"]);
      return { noun, text: matched ? `${matched} matched` : str(d["summary"]) || "event search" };
    }
    case "process_info": {
      const svc = obj(d["service"]);
      if (svc) return { noun, text: `${str(svc["name"]) ?? "service"}: ${str(svc["state"]) ?? "?"}` };
      const n = arr(d["processes"]).length;
      return { noun, text: n > 0 ? `${n} process${n === 1 ? "" : "s"} snapshotted` : "process snapshot" };
    }
    case "scheduled_tasks": {
      const n = arr(d["tasks"]).length;
      return { noun, text: n > 0 ? `${n} task${n === 1 ? "" : "s"} listed` : "no tasks listed" };
    }
    case "demo_worker": {
      const s = str(d["status"]);
      return { noun, text: s ? `worker ${s}` : "worker reading" };
    }
    case "error_code": {
      const name = str(d["name"]);
      return { noun, text: name ?? str(d["hex"]) ?? "code decoded" };
    }
    case "os_info":
      return { noun, text: str(d["caption"]) ?? "system reading" };
    default:
      return { noun, text: str(d["summary"]) || `${item.category.replace(/_/g, " ")} reading` };
  }
}
