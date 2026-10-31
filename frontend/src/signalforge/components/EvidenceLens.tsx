import { useMemo } from "react";
import {
  LENS_MAX_CHANGE_ROWS,
  buildRefreshPairs,
  contradictionsFor,
  hostLabel,
  lensCounts,
  recordHost,
  recordStatus,
  shortHostHash,
  snapshotCompare,
  sortEvidenceRecords,
  type LensHost,
  type LensPair,
  type LensSnapshot,
} from "../../evidenceLens";
import type { EvidenceItem, InvestigationResponse } from "../../types";

export type EvidenceLensProps = {
  investigation: InvestigationResponse;
  /** Drill through to the existing record inspector. */
  onInspectRecord?: (id: string) => void;
};

function fmtTime(when: string | null | undefined): string {
  if (!when) return "—";
  const date = new Date(when);
  if (Number.isNaN(date.getTime())) return when;
  return date.toLocaleString();
}

function VerdictToken({ verdict }: { verdict: string }) {
  const cls =
    verdict === "changed"
      ? "sf-lens-verdict sf-lens-changed"
      : verdict === "unchanged"
        ? "sf-lens-verdict sf-lens-unchanged"
        : "sf-lens-verdict sf-lens-unavailable";
  return <span className={cls}>{verdict.toUpperCase()}</span>;
}

function RecordRow({
  item,
  host,
  contradictionCount,
  onInspectRecord,
}: {
  item: EvidenceItem;
  host: LensHost;
  contradictionCount: number;
  onInspectRecord?: (id: string) => void;
}) {
  const status = recordStatus(item);
  return (
    <li className="sf-lens-row" data-testid="lens-record-row" data-record-id={item.id}>
      <span className={`sf-lens-status sf-lens-status-${status}`} aria-label={`Status: ${status}`}>
        {status.toUpperCase()}
      </span>
      <span className="sf-lens-row-main">
        <strong>{item.tool_name ?? item.category}</strong>
        <small>
          {item.source} &middot; {fmtTime(item.collected_at)}
        </small>
        <small className="sf-lens-host">{hostLabel(host)}</small>
        {contradictionCount > 0 && (
          <small className="sf-lens-cx">
            cited by {contradictionCount} contradiction{contradictionCount === 1 ? "" : "s"}
          </small>
        )}
      </span>
      <span className="sf-lens-row-id">{item.id}</span>
      {onInspectRecord && (
        <button
          type="button"
          className="sf-btn sf-btn-dark sf-btn-sm"
          onClick={() => onInspectRecord(item.id)}
          aria-label={`Inspect record ${item.id}`}
        >
          Inspect
        </button>
      )}
    </li>
  );
}

function PairCard({ pair, onInspectRecord }: { pair: LensPair; onInspectRecord?: (id: string) => void }) {
  const { refresh, oldItem, newItem, resolution, refreshOfAgrees, diff } = pair;
  const shownChanged = diff.rows.filter((row) => row.state === "changed").slice(0, LENS_MAX_CHANGE_ROWS);
  const hiddenChanged = diff.rows.filter((row) => row.state === "changed").length - shownChanged.length;
  const unchangedRows = diff.rows.filter((row) => row.state === "unchanged");
  const unknownRows = diff.rows.filter((row) => row.state === "unknown");
  const inspect = (id: string | null) =>
    id !== null && onInspectRecord ? (
      <button
        type="button"
        className="sf-lens-idbtn"
        onClick={() => onInspectRecord(id)}
        aria-label={`Inspect record ${id}`}
      >
        {id}
      </button>
    ) : (
      <span className="sf-lens-row-id">{id ?? "(collection failed)"}</span>
    );

  return (
    <li className="sf-lens-pair" data-testid="lens-pair">
      <div className="sf-lens-pair-head">
        <VerdictToken verdict={refresh.verdict} />
        <span className="sf-lens-pair-link">
          {inspect(refresh.old_evidence_id)}
          <span aria-hidden="true"> → </span>
          {inspect(refresh.new_evidence_id)}
        </span>
        <code className="sf-lens-tool">{refresh.tool_name}</code>
      </div>
      <p className="sf-lens-times">
        Historical: {fmtTime(refresh.old_collected_at)} &middot; Current:{" "}
        {fmtTime(refresh.new_collected_at)} &middot; Compared: {fmtTime(refresh.compared_at)}
      </p>
      {refreshOfAgrees === false && (
        <p className="sf-lens-warn">
          Warning: the new record&apos;s refresh_of link does not point at the historical record.
          The verdict above is kept from the stored comparison.
        </p>
      )}
      {resolution === "missing-old" && (
        <p className="sf-lens-warn">Unknown — the historical record is not on this case.</p>
      )}
      {resolution === "missing-new" && (
        <p className="sf-lens-warn">Unknown — the current record is not on this case.</p>
      )}
      {resolution === "failed-new" && newItem !== null && newItem.error && (
        <p className="sf-lens-warn">Re-check failed to collect: {newItem.error}</p>
      )}
      {resolution === "failed-new" && newItem === null && (
        <p className="sf-lens-warn">Re-check failed to collect a new reading.</p>
      )}
      {refresh.changes.length > 0 && (
        <ul className="sf-lens-changes">
          {refresh.changes.map((change, index) => (
            <li key={index}>
              <code>{change}</code>
            </li>
          ))}
        </ul>
      )}
      {resolution === "ok" && oldItem !== null && newItem !== null && (
        <div className="sf-lens-fields">
          <p>
            Measured fields: {diff.changed} changed &middot; {diff.unchanged} unchanged
            {diff.unknown > 0 ? ` · ${diff.unknown} unknown` : ""}
            {diff.truncated ? " · bounded comparison, further fields not compared" : ""}.
          </p>
          {shownChanged.length > 0 && (
            <table className="sf-lens-table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Before ({oldItem.id})</th>
                  <th scope="col">After ({newItem.id})</th>
                </tr>
              </thead>
              <tbody>
                {shownChanged.map((row) => (
                  <tr key={row.path}>
                    <th scope="row">{row.path}</th>
                    <td>{row.before ?? "(absent)"}</td>
                    <td>{row.after ?? "(absent)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {hiddenChanged > 0 && <p>…and {hiddenChanged} more changed fields.</p>}
          {shownChanged.length === 0 && unknownRows.length === 0 && (
            <p>No measured field differs between the two readings.</p>
          )}
          {unknownRows.map((row) => (
            <p key={row.path}>
              Unknown: {row.after ?? "a record could not be compared"}.
            </p>
          ))}
          {unchangedRows.length > 0 && (
            <details>
              <summary>Show {unchangedRows.length} unchanged fields</summary>
              <ul className="sf-lens-unchanged">
                {unchangedRows.map((row) => (
                  <li key={row.path}>
                    <code>{row.path}</code>: {row.before ?? "(absent)"}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
      {refresh.affected_causes.length > 0 && (
        <p className="sf-lens-warn">
          Hypotheses built on the old reading may need review: {refresh.affected_causes.join("; ")}
        </p>
      )}
    </li>
  );
}

function SnapshotSection({
  snapshot,
  onInspectRecord,
}: {
  snapshot: LensSnapshot;
  onInspectRecord?: (id: string) => void;
}) {
  if (snapshot.state === "no-packages") {
    return <p>No Collector snapshots on this case — nothing to compare.</p>;
  }
  if (snapshot.state === "single-snapshot") {
    return (
      <p>
        Only one Collector snapshot on this case ({snapshot.package.package_id},{" "}
        {shortHostHash(snapshot.package.hostname_hash)},{" "}
        {fmtTime(snapshot.package.created_at)}) — a comparison needs two snapshots from the same
        computer. No differences are inferred from a single snapshot.
      </p>
    );
  }
  if (snapshot.state === "host-mismatch") {
    return (
      <p>
        Not comparable — the two snapshots describe different computers (
        {shortHostHash(snapshot.packageA.hostname_hash)} vs{" "}
        {shortHostHash(snapshot.packageB.hostname_hash)}). Readings from different machines are
        never diffed against each other.
      </p>
    );
  }
  if (snapshot.state === "insufficient-evidence") {
    return (
      <div>
        <p>
          {snapshot.packageA.package_id} → {snapshot.packageB.package_id} (
          {shortHostHash(snapshot.packageA.hostname_hash)}): insufficient evidence — no stored
          re-collection links any reading in the older snapshot to the newer one, so there is
          nothing truthful to compare.
        </p>
        <dl className="sf-kv">
          <dt>Older snapshot</dt>
          <dd>
            {snapshot.packageA.package_id} · {fmtTime(snapshot.packageA.created_at)}
          </dd>
          <dt>Newer snapshot</dt>
          <dd>
            {snapshot.packageB.package_id} · {fmtTime(snapshot.packageB.created_at)}
          </dd>
        </dl>
      </div>
    );
  }
  return (
    <div>
      <p>
        {snapshot.pairs.length} linked reading{snapshot.pairs.length === 1 ? "" : "s"} between two
        snapshots from {shortHostHash(snapshot.hostHash)}
        {snapshot.total > 2 ? ` (the two most recent of ${snapshot.total} snapshots)` : ""}.
      </p>
      <dl className="sf-kv">
        <dt>Older snapshot</dt>
        <dd>
          {snapshot.packageA.package_id} · {fmtTime(snapshot.packageA.created_at)}
        </dd>
        <dt>Newer snapshot</dt>
        <dd>
          {snapshot.packageB.package_id} · {fmtTime(snapshot.packageB.created_at)}
        </dd>
      </dl>
      <ol className="sf-lens-pairs">
        {snapshot.pairs.map((pair) => (
          <PairCard
            key={`${pair.refresh.old_evidence_id}-${pair.refresh.compared_at}`}
            pair={pair}
            onInspectRecord={onInspectRecord}
          />
        ))}
      </ol>
    </div>
  );
}

export function EvidenceLens({ investigation, onInspectRecord }: EvidenceLensProps) {
  const records = useMemo(() => sortEvidenceRecords(investigation.evidence), [investigation.evidence]);
  const pairs = useMemo(() => buildRefreshPairs(investigation), [investigation]);
  const snapshot = useMemo(() => snapshotCompare(investigation), [investigation]);
  const counts = useMemo(() => lensCounts(investigation), [investigation]);
  const contradictions = Array.isArray(investigation.contradictions)
    ? investigation.contradictions
    : [];

  return (
    <div data-testid="evidence-lens" aria-label="Evidence Lens">
      <div className="sf-utility-card" data-testid="lens-records">
        <h2>Records under the lens</h2>
        <p>
          {counts.records} records on this case
          {counts.failed > 0 ? ` · ${counts.failed} failed to collect` : " · none failed to collect"}
          . Ordered by collection time, then record id.
        </p>
        {records.length === 0 ? (
          <p>No records on this case yet — diagnostic results land here as they are collected.</p>
        ) : (
          <ol className="sf-lens-rows">
            {records.map((item) => (
              <RecordRow
                key={item.id}
                item={item}
                host={recordHost(item, investigation)}
                contradictionCount={contradictionsFor(item.id, contradictions).length}
                onInspectRecord={onInspectRecord}
              />
            ))}
          </ol>
        )}
      </div>

      <div className="sf-utility-card" data-testid="lens-refreshes">
        <h2>Re-checks ({pairs.length})</h2>
        {pairs.length === 0 ? (
          <p>
            No re-checks yet — re-collect a record to compare a historical reading against a fresh
            one. History is preserved; nothing is overwritten.
          </p>
        ) : (
          <ol className="sf-lens-pairs">
            {pairs.map((pair) => (
              <PairCard
                key={`${pair.refresh.old_evidence_id}-${pair.refresh.compared_at}`}
                pair={pair}
                onInspectRecord={onInspectRecord}
              />
            ))}
          </ol>
        )}
      </div>

      <div className="sf-utility-card" data-testid="lens-snapshots">
        <h2>Snapshot compare</h2>
        <SnapshotSection snapshot={snapshot} onInspectRecord={onInspectRecord} />
      </div>

      <div className="sf-utility-card" data-testid="lens-contradictions">
        <h2>Contradictions ({contradictions.length})</h2>
        {contradictions.length === 0 ? (
          <p>No contradictions between current observations.</p>
        ) : (
          <ol className="sf-lens-cxlist">
            {contradictions.map((entry) => (
              <li key={entry.contradiction_id}>
                <p>{entry.description}</p>
                <p>
                  Cites:{" "}
                  {entry.evidence_ids.map((id, index) => (
                    <span key={id}>
                      {index > 0 ? ", " : ""}
                      {onInspectRecord ? (
                        <button
                          type="button"
                          className="sf-lens-idbtn"
                          onClick={() => onInspectRecord(id)}
                          aria-label={`Inspect record ${id}`}
                        >
                          {id}
                        </button>
                      ) : (
                        <span className="sf-lens-row-id">{id}</span>
                      )}
                    </span>
                  ))}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
