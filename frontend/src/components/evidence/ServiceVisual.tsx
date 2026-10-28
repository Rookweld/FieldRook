import type { EvidenceItem } from "../../types";
import { arr, fmt, obj, SectionTitle, SliceNote, StateDot, StatePill, str } from "./shared";

/** Single-service status module. */
function SingleService({ item }: { item: EvidenceItem }) {
  const d = item.data;
  const status = obj(d["status"]);
  const startup = obj(d["startup"]);
  const name = str(d["name"]) ?? str(status?.["name"]);
  const display = str(d["display_name"]) ?? str(status?.["display_name"]);
  const state = str(status?.["status"]) ?? str(d["status"]) ?? str(d["state"]);
  const startType = str(startup?.["startup_type"]) ?? str(d["startup_type"]);
  const runsAs = str(startup?.["start_name"]) ?? str(d["start_name"]);
  const pid = d["pid"] ?? status?.["pid"];
  const svcType = str(status?.["service_type"]) ?? str(d["service_type"]);
  const deps = arr(d["dependencies"] ?? d["depends_on"]).filter(
    (x): x is string => typeof x === "string" && x !== "",
  );
  const manualStopped =
    (state ?? "").toLowerCase() === "stopped" && (startType ?? "").toLowerCase() === "manual";

  return (
    <div className="svc">
      <div className="svc-head">
        <div>
          <p className="svc-name">{name ?? "Unknown service"}</p>
          {display && display !== name && <p className="muted">{display}</p>}
        </div>
        <StatePill state={state} />
      </div>
      <dl className="fact-grid">
        {startType && (
          <div className="fact">
            <dt>Start type</dt>
            <dd>{startType}</dd>
          </div>
        )}
        {runsAs && (
          <div className="fact">
            <dt>Runs as</dt>
            <dd>{runsAs}</dd>
          </div>
        )}
        {pid !== null && pid !== undefined && (
          <div className="fact">
            <dt>PID</dt>
            <dd className="mono">{fmt(pid)}</dd>
          </div>
        )}
        {svcType && (
          <div className="fact">
            <dt>Service type</dt>
            <dd>{svcType}</dd>
          </div>
        )}
      </dl>
      {deps.length > 0 && (
        <>
          <SectionTitle>Dependencies ({deps.length})</SectionTitle>
          <ul className="chip-list">
            {deps.slice(0, 12).map((dep) => (
              <li key={dep}>
                <code className="chip">{dep}</code>
              </li>
            ))}
          </ul>
          <SliceNote shown={Math.min(deps.length, 12)} total={deps.length} what="dependencies" />
        </>
      )}
      {manualStopped && (
        <p className="muted svc-note">
          Stopped + Manual is normal idle behavior for on-demand services — not
          evidence of a fault by itself.
        </p>
      )}
    </div>
  );
}

/** Multi-service list module. */
function ServiceList({ item }: { item: EvidenceItem }) {
  const services = arr(item.data["services"]).map(obj).filter((o) => o !== null);
  const stopped = services.filter((s) => str(s["status"]) === "Stopped");
  const running = services.length - stopped.length;
  return (
    <div className="svc">
      <p className="muted">{str(item.data["summary"]) ?? `${services.length} services listed.`}</p>
      <div className="svc-tally" aria-label={`${running} running, ${stopped.length} stopped`}>
        <span className="tally tally-on">
          <StateDot state="Running" /> {running} running
        </span>
        <span className="tally">
          <StateDot state="Stopped" /> {stopped.length} stopped
        </span>
      </div>
      {services.length > 0 && (
        <ul className="svc-rows">
          {services.slice(0, 10).map((s, i) => (
            <li key={`${str(s["name"]) ?? i}`}>
              <StateDot state={str(s["status"])} />
              <code className="mono">{str(s["name"]) ?? "?"}</code>
              {str(s["display_name"]) && str(s["display_name"]) !== str(s["name"]) && (
                <span className="muted">{str(s["display_name"])}</span>
              )}
              <span className="svc-state muted">{str(s["status"]) ?? "unknown"}</span>
            </li>
          ))}
        </ul>
      )}
      <SliceNote shown={Math.min(services.length, 10)} total={services.length} what="services" />
    </div>
  );
}

export function ServiceVisual({ item }: { item: EvidenceItem }) {
  if (item.category === "service_list") return <ServiceList item={item} />;
  return <SingleService item={item} />;
}
