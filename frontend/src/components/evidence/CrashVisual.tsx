import type { EvidenceItem } from "../../types";
import { EmptyState } from "../EmptyState";
import { arr, obj, SliceNote, str } from "./shared";

type Crash = {
  id: string | null;
  app: string | null;
  exception: string | null;
  module: string | null;
  time: string | null;
  sortKey: number;
};

function toCrash(o: Record<string, unknown>): Crash {
  const time = str(o["time_created"]);
  const parsed = time ? Date.parse(time) : NaN;
  return {
    id: str(o["id"]),
    app: str(o["app_name"]),
    exception: str(o["exception_code"]),
    module: str(o["faulting_module"]),
    time,
    sortKey: Number.isNaN(parsed) ? -1 : parsed,
  };
}

/** Crash records as a newest-first incident list. Order is explicit. */
export function CrashVisual({ item }: { item: EvidenceItem }) {
  const crashes = arr(item.data["crashes"])
    .map(obj)
    .filter((o): o is Record<string, unknown> => o !== null)
    .map(toCrash)
    .sort((a, b) => b.sortKey - a.sortKey);
  const summary = str(item.data["summary"]);

  if (crashes.length === 0) {
    return (
      <div className="crash">
        {summary && <p className="muted">{summary}</p>}
        <EmptyState
          icon="◇"
          title="No crash records in this reading"
          body="The search completed but matched nothing. Widen the time window or check the application name, then investigate again."
        />
      </div>
    );
  }

  return (
    <div className="crash">
      {summary && <p className="muted">{summary}</p>}
      <p className="muted crash-order">
        {crashes.length} record{crashes.length === 1 ? "" : "s"} · newest first
      </p>
      <ol className="crash-list">
        {crashes.slice(0, 5).map((c, i) => (
          <li key={`${c.id ?? "x"}-${i}`} className="crash-card">
            <div className="crash-head">
              <strong>{c.app ?? "Unknown application"}</strong>
              {c.id && <code className="mono muted">event {c.id}</code>}
            </div>
            <div className="crash-codes">
              {c.exception && <code className="mono crash-code">{c.exception}</code>}
              {c.module && (
                <span className="muted">
                  in <code className="mono">{c.module}</code>
                </span>
              )}
            </div>
            {c.time && <p className="mono muted crash-time">{c.time}</p>}
          </li>
        ))}
      </ol>
      <SliceNote shown={Math.min(crashes.length, 5)} total={crashes.length} what="crash records" />
    </div>
  );
}
