import type { EvidenceItem } from "../../types";
import { arr, FactGrid, fmt, obj, SectionTitle, SliceNote, StateDot, StatePill, str } from "./shared";
import { summarizeEvidence } from "../../evidenceSummary";

function ProcessInfo({ item }: { item: EvidenceItem }) {
  const d = item.data;
  const service = obj(d["service"]);
  const processes = arr(d["processes"]).map(obj).filter((o): o is Record<string, unknown> => o !== null);
  return (
    <div className="ops">
      {str(d["summary"]) && <p className="muted">{str(d["summary"])}</p>}
      {service && (
        <div className="ops-link">
          <StateDot state={str(service["state"])} />
          <code className="mono">{str(service["name"]) ?? "service"}</code>
          <span className="muted">{str(service["state"]) ?? "unknown state"}</span>
          {service["pid"] !== null && service["pid"] !== undefined && (
            <span className="mono muted">pid {fmt(service["pid"])}</span>
          )}
        </div>
      )}
      {processes.length > 0 && (
        <>
          <SectionTitle>Processes ({processes.length})</SectionTitle>
          <ul className="ops-rows">
            {processes.slice(0, 6).map((p, i) => (
              <li key={`${str(p["name"]) ?? i}`}>
                <code className="mono">{str(p["name"]) ?? "?"}</code>
                {p["memory_mb"] !== undefined && (
                  <span className="mono muted">{fmt(p["memory_mb"])} MB</span>
                )}
                {str(p["started"]) && <span className="mono muted">since {str(p["started"])}</span>}
              </li>
            ))}
          </ul>
          <SliceNote shown={Math.min(processes.length, 6)} total={processes.length} what="processes" />
        </>
      )}
    </div>
  );
}

function TaskList({ item }: { item: EvidenceItem }) {
  const tasks = arr(item.data["tasks"]).map(obj).filter((o): o is Record<string, unknown> => o !== null);
  return (
    <div className="ops">
      {str(item.data["summary"]) && <p className="muted">{str(item.data["summary"])}</p>}
      <ul className="ops-rows task-rows">
        {tasks.slice(0, 6).map((t, i) => {
          const state = str(t["state"]) ?? str(t["enabled"]);
          return (
            <li key={`${str(t["task_name"]) ?? i}`}>
              <StateDot state={state} />
              <code className="mono">{str(t["task_name"]) ?? "task"}</code>
              <span className="muted">{state ?? "unknown"}</span>
              {str(t["author"]) && <span className="muted">by {str(t["author"])}</span>}
              {str(t["last_run"]) && <span className="mono muted">last {str(t["last_run"])}</span>}
            </li>
          );
        })}
      </ul>
      <SliceNote shown={Math.min(tasks.length, 6)} total={tasks.length} what="tasks" />
    </div>
  );
}

function WorkerStatus({ item }: { item: EvidenceItem }) {
  const d = item.data;
  const status = str(d["status"]);
  const hb = d["heartbeat_age_s"];
  const verified = d["process_verified"];
  return (
    <div className="ops">
      <div className="svc-head">
        <div>
          <p className="svc-name">{str(d["worker_id"]) ?? "demo worker"}</p>
          {str(d["detail"]) && <p className="muted">{str(d["detail"])}</p>}
        </div>
        <StatePill state={status} />
      </div>
      <dl className="fact-grid">
        {hb !== null && hb !== undefined && (
          <div className="fact">
            <dt>Heartbeat age</dt>
            <dd className="mono">{fmt(hb)}s</dd>
          </div>
        )}
        {verified !== undefined && (
          <div className="fact">
            <dt>Process verified</dt>
            <dd>{verified === true ? "yes" : verified === false ? "no" : "—"}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function ErrorCode({ item }: { item: EvidenceItem }) {
  const d = item.data;
  return (
    <div className="ops errcode">
      <div className="errcode-head">
        <code className="mono crash-code">{str(d["hex"]) ?? str(d["input"]) ?? "?"}</code>
        {str(d["name"]) && <strong>{str(d["name"])}</strong>}
      </div>
      {str(d["description"]) && <p>{str(d["description"])}</p>}
      <dl className="fact-grid">
        {str(d["input"]) && (
          <div className="fact">
            <dt>Input</dt>
            <dd className="mono">{str(d["input"])}</dd>
          </div>
        )}
        {str(d["family"]) && (
          <div className="fact">
            <dt>Family</dt>
            <dd>{str(d["family"])}</dd>
          </div>
        )}
        {str(d["note"]) && (
          <div className="fact">
            <dt>Note</dt>
            <dd>{str(d["note"])}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

/** Clean generic fallback: summary + fact grid, raw JSON stays one click away. */
export function GenericVisual({ item }: { item: EvidenceItem }) {
  const rows = summarizeEvidence(item);
  return (
    <div className="ops">
      <FactGrid rows={rows} />
    </div>
  );
}

export function OpsVisual({ item }: { item: EvidenceItem }) {
  switch (item.category) {
    case "process_info":
      return <ProcessInfo item={item} />;
    case "scheduled_tasks":
      return <TaskList item={item} />;
    case "demo_worker":
      return <WorkerStatus item={item} />;
    case "error_code":
      return <ErrorCode item={item} />;
    default:
      return <GenericVisual item={item} />;
  }
}
