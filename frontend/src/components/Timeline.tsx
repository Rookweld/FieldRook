import type { ActivityRecord } from "../types";

const KIND_MARK: Record<ActivityRecord["kind"], string> = {
  plan: "\u25B8",
  tool_request: "\u2699",
  tool_result: "\u2713",
  evidence: "\u25C6",
  note: "\u2139",
  reverify: "\u21BB",
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

interface Round {
  n: number;
  label: string;
  records: ActivityRecord[];
}

function groupRounds(activity: ActivityRecord[]): Round[] {
  const rounds: Round[] = [{ n: 1, label: "Round 1 — initial investigation", records: [] }];
  for (const record of activity) {
    if (record.kind === "note" && record.title === "Follow-up received") {
      rounds.push({
        n: rounds.length + 1,
        label: `Round ${rounds.length + 1} — follow-up`,
        records: [record],
      });
    } else if (record.kind === "tool_request" && record.title.startsWith("Reverify requested")) {
      rounds.push({
        n: rounds.length + 1,
        label: `Round ${rounds.length + 1} — re-check`,
        records: [record],
      });
    } else if (
      record.kind === "tool_request" &&
      (record.title.startsWith("Plan baseline:") ||
        record.title.startsWith("Plan verification:"))
    ) {
      // M010-7: each plan baseline / Confirm Fix run is its own round, but
      // consecutive tools within one run stay grouped together.
      const label = record.title.startsWith("Plan baseline:")
        ? "pre-fix baseline"
        : "Confirm Fix verification";
      const last = rounds[rounds.length - 1];
      const prev = last.records[last.records.length - 1];
      const continuesRun =
        prev !== undefined &&
        (prev.title.startsWith("Plan baseline:") ||
          prev.title.startsWith("Plan verification:"));
      if (last.label.endsWith(label) && continuesRun) {
        last.records.push(record);
      } else {
        rounds.push({
          n: rounds.length + 1,
          label: `Round ${rounds.length + 1} — ${label}`,
          records: [record],
        });
      }
    } else {
      rounds[rounds.length - 1].records.push(record);
    }
  }
  return rounds;
}

function RecordItem({ record }: { record: ActivityRecord }) {
  return (
    <li className={`tl tl-${record.kind}`}>
      <span className="tl-mark" aria-hidden="true">
        {KIND_MARK[record.kind]}
      </span>
      <div className="tl-body">
        <div className="tl-title">
          <span className="tl-seq">#{record.seq}</span> {record.title}
          {record.duration_ms !== null &&
            record.duration_ms !== undefined &&
            // M011: several producers already end the title with "Nms".
            !record.title.includes(`${record.duration_ms}ms`) && (
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
  );
}

export function Timeline({ activity }: { activity: ActivityRecord[] }) {
  if (activity.length === 0) return null;
  const rounds = groupRounds(activity);
  return (
    <section className="card">
      <div className="card-head">
        <h2>Diagnostic activity</h2>
        <span className="muted">
          {activity.length} records · {rounds.length} round{rounds.length === 1 ? "" : "s"}
        </span>
      </div>
      {rounds.map((round) => (
        <div key={round.n}>
          {rounds.length > 1 && <h3 className="round-head">{round.label}</h3>}
          <ol className="timeline">
            {round.records.map((record) => (
              <RecordItem key={record.seq} record={record} />
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}


