import type { EvidenceItem } from "../../types";
import { EmptyState } from "../EmptyState";
import { arr, LevelBadge, obj, SectionTitle, SliceNote, str } from "./shared";

type LogEvent = {
  id: string | null;
  level: string | null;
  provider: string | null;
  message: string | null;
  time: string | null;
};

function toEvent(o: Record<string, unknown>): LogEvent {
  return {
    id: str(o["id"]),
    level: str(o["level"]),
    provider: str(o["provider"]),
    message: str(o["message"]),
    time: str(o["time_created"]),
  };
}

export function EventLogVisual({ item }: { item: EvidenceItem }) {
  const logs = arr(item.data["logs"]).map(obj).filter((o): o is Record<string, unknown> => o !== null);
  const summary = str(item.data["summary"]);
  const scanned = str(item.data["scanned"]);
  const matched = str(item.data["matched"]);

  if (logs.length === 0) {
    return (
      <div className="evlog">
        {summary && <p className="muted">{summary}</p>}
        <EmptyState
          icon="◇"
          title="No matching events"
          body="The log search completed without matches. This rules out the searched patterns — it does not prove the log is clean."
        />
      </div>
    );
  }

  return (
    <div className="evlog">
      {summary && <p className="muted">{summary}</p>}
      {(scanned || matched) && (
        <p className="muted">
          {scanned && `examined ${scanned}`}
          {scanned && matched && " · "}
          {matched && `${matched} matched`}
        </p>
      )}
      {logs.slice(0, 3).map((log, li) => {
        const events = arr(log["events"]).map(obj).filter((o): o is Record<string, unknown> => o !== null).map(toEvent);
        const logName = str(log["log"]) ?? str(log["name"]) ?? `Log ${li + 1}`;
        return (
          <div key={`${logName}-${li}`}>
            <SectionTitle>
              {logName} ({events.length})
            </SectionTitle>
            <ol className="evlog-list">
              {events.slice(0, 4).map((ev, i) => {
                const long = (ev.message ?? "").length > 160;
                return (
                  <li key={i} className="evlog-row">
                    <div className="evlog-head">
                      <LevelBadge level={ev.level} />
                      {ev.id && <code className="mono">ID {ev.id}</code>}
                      {ev.provider && <span className="muted">{ev.provider}</span>}
                      {ev.time && <span className="mono muted evlog-time">{ev.time}</span>}
                    </div>
                    {long ? (
                      <details className="evlog-msg">
                        <summary>{ev.message?.slice(0, 160)}…</summary>
                        <p>{ev.message}</p>
                      </details>
                    ) : (
                      ev.message && <p className="evlog-msg">{ev.message}</p>
                    )}
                  </li>
                );
              })}
            </ol>
            <SliceNote shown={Math.min(events.length, 4)} total={events.length} what="events" />
          </div>
        );
      })}
      <SliceNote shown={Math.min(logs.length, 3)} total={logs.length} what="logs" />
    </div>
  );
}
