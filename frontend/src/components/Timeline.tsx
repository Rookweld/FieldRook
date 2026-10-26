import type { ActivityRecord } from "../types";

const KIND_MARK: Record<ActivityRecord["kind"], string> = {
  plan: "\u25B8",
  tool_request: "\u2699",
  tool_result: "\u2713",
  evidence: "\u25C6",
  note: "\u2139",
  proposed: "\u2696",
  approval_requested: "\u2696",
  approved: "\u2714",
  rejected: "\u2716",
  executed: "\u25B6",
  verification_started: "\u25CC",
  verified: "\u25C9",
  done: "\u2714",
  error: "\u2716",
};

export function Timeline({ activity }: { activity: ActivityRecord[] }) {
  if (activity.length === 0) return null;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Diagnostic activity</h2>
        <span className="muted">{activity.length} records</span>
      </div>
      <ol className="timeline">
        {activity.map((record) => (
          <li key={record.seq} className={`tl tl-${record.kind}`}>
            <span className="tl-mark" aria-hidden="true">
              {KIND_MARK[record.kind]}
            </span>
            <div className="tl-body">
              <div className="tl-title">
                <span className="tl-seq">#{record.seq}</span> {record.title}
                {record.duration_ms !== null && record.duration_ms !== undefined && (
                  <span className="muted"> ({record.duration_ms}ms)</span>
                )}
              </div>
              {record.detail && <p className="tl-detail">{record.detail}</p>}
              {record.evidence_ids.length > 0 && (
                <div className="tl-refs">
                  {record.evidence_ids.map((eid) => (
                    <code key={eid} className="chip">
                      {eid}
                    </code>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
