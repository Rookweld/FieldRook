import { useEffect, useState } from "react";
import type { EvidenceItem } from "../../types";
import { useNetworkLab } from "../hooks/useNetworkLab";
import {
  MAX_ROWS,
  asList,
  asRecord,
  isTruncated,
  networkSections,
  parseSource,
  recheckAvailability,
  targetBanner,
  text,
  type NetworkSection,
  type NetworkSectionSpec,
} from "../networkLab";
import type { NetworkLabProps } from "../types";
import "./Utility.css";

function formatWhen(value: string): string {
  const time = new Date(value);
  return Number.isNaN(time.getTime()) ? value : time.toLocaleString();
}

function join(parts: (string | null)[]): string | null {
  const kept = parts.filter((part): part is string => part !== null && part !== "");
  return kept.length > 0 ? kept.join(" · ") : null;
}

function summarizeRecord(category: NetworkSectionSpec["category"], value: unknown): string {
  const row = asRecord(value);
  if (!row) return "Unrecognized record shape (see raw data).";
  switch (category) {
    case "net_adapters":
      return (
        join([
          text(row["name"]),
          text(row["status"]),
          text(row["link_speed"]),
          text(row["mac_address"]),
        ]) ?? "Adapter record"
      );
    case "ip_config":
      return (
        join([
          text(row["interface"]),
          text(row["ip_address"]),
          row["prefix_length"] !== undefined && row["prefix_length"] !== null
            ? `/${String(row["prefix_length"])}`
            : null,
          text(row["address_family"]),
          text(row["prefix_origin"]),
        ]) ?? "Address record"
      );
    case "dns_config": {
      const servers = asList(row["servers"])
        .map(text)
        .filter((s): s is string => s !== null);
      return `${text(row["interface"]) ?? "Interface"}: ${servers.length > 0 ? servers.join(", ") : "(no servers)"}`;
    }
    case "connections": {
      const local = join([
        text(row["local_address"]) ?? text(row["local"]),
        row["local_port"] !== undefined && row["local_port"] !== null
          ? `port ${String(row["local_port"])}`
          : null,
      ]);
      const remote = join([
        text(row["remote_address"]) ?? text(row["remote"]),
        row["remote_port"] !== undefined && row["remote_port"] !== null
          ? `port ${String(row["remote_port"])}`
          : null,
      ]);
      return (
        join([
          local && remote ? `${local} → ${remote}` : (local ?? remote),
          text(row["state"]),
          row["owning_process_id"] !== undefined && row["owning_process_id"] !== null
            ? `pid ${String(row["owning_process_id"])}`
            : null,
        ]) ?? "Connection record"
      );
    }
    case "dns_test":
      return "Resolution record";
  }
}

function sectionListKey(section: NetworkSection): string {
  switch (section.category) {
    case "net_adapters":
      return "adapters";
    case "ip_config":
      return "addresses";
    case "dns_config":
      return "interfaces";
    case "connections":
      return "connections";
    case "dns_test":
      return "addresses";
  }
}

function RecordBody({ item, section }: { item: EvidenceItem; section: NetworkSection }) {
  const data = asRecord(item.data) ?? {};
  if (item.error) {
    return (
      <dl className="sf-kv">
        <dt>Error</dt>
        <dd>{item.error}</dd>
      </dl>
    );
  }
  if (isTruncated(data)) {
    return (
      <dl className="sf-kv">
        <dt>Result</dt>
        <dd>{text(data["summary"]) ?? "Large result, showing a preview."}</dd>
        <dt>Full size</dt>
        <dd>{text(data["total_chars"]) ?? "?"} chars (see raw data)</dd>
      </dl>
    );
  }
  if (section.category === "dns_test") {
    const succeeded = data["succeeded"];
    const addresses = asList(data["addresses"])
      .map(text)
      .filter((s): s is string => s !== null);
    return (
      <dl className="sf-kv">
        <dt>Host</dt>
        <dd>{text(data["hostname"]) ?? "—"}</dd>
        <dt>Resolves</dt>
        <dd>{succeeded === true ? "yes" : succeeded === false ? "no" : "unknown"}</dd>
        <dt>Addresses</dt>
        <dd>{addresses.length > 0 ? addresses.join(", ") : "—"}</dd>
        <dt>Query time</dt>
        <dd>
          {data["query_ms"] !== undefined && data["query_ms"] !== null
            ? `${String(data["query_ms"])} ms`
            : "—"}
        </dd>
        {text(data["error"]) && (
          <>
            <dt>Detail</dt>
            <dd>{text(data["error"])}</dd>
          </>
        )}
      </dl>
    );
  }
  const rows = asList(data[sectionListKey(section)]);
  if (rows.length === 0) {
    return <p>{text(data["summary"]) ?? "No records in this reading."}</p>;
  }
  const shown = rows.slice(0, MAX_ROWS);
  return (
    <>
      <ul>
        {shown.map((row, index) => (
          <li key={index}>{summarizeRecord(section.category, row)}</li>
        ))}
      </ul>
      {rows.length > shown.length && <p>+{rows.length - shown.length} more (see raw data).</p>}
    </>
  );
}

function RecheckControl({
  item,
  spec,
  target,
  consented,
  busy,
  onRecheck,
}: {
  item: EvidenceItem;
  spec: NetworkSectionSpec;
  target: "local" | "remote" | "unknown";
  consented: boolean;
  busy: boolean;
  onRecheck: () => void;
}) {
  const availability = recheckAvailability(item, target);
  if (!availability.allowed) {
    // No Run control at all when a re-check is impossible: remote/unknown
    // targets and imported records get an honest reason, not a dead button.
    return <p>{availability.reason}</p>;
  }
  return (
    <>
      <button
        type="button"
        className="sf-btn sf-btn-dark sf-btn-sm"
        data-testid={`network-recheck-${item.id}`}
        disabled={!consented || busy}
        title={
          consented
            ? `Re-run ${spec.tool} read-only on this computer`
            : "Tick the consent box above to enable read-only re-checks on this computer"
        }
        onClick={onRecheck}
      >
        {busy ? "Checking…" : consented ? `Re-check (${spec.tool})` : "Re-check (needs consent)"}
      </button>
      {spec.activeTest && (
        <p>Active test: sends one real DNS query for the stored hostname. Changes nothing.</p>
      )}
    </>
  );
}

export function NetworkLab({
  investigation,
  onUpdate,
  onGoWorkbench,
  onGoLaunchpad,
  onGoEvidence,
}: NetworkLabProps) {
  const [consented, setConsented] = useState(false);
  const { busyId, error, notice, recheck, cancel, refresh, clearStatus } = useNetworkLab({
    investigation,
    onUpdate,
  });

  // Consent is per-visit and per-case: never persisted, reset on case change.
  useEffect(() => {
    setConsented(false);
    clearStatus();
  }, [investigation?.investigation_id, clearStatus]);

  if (!investigation) {
    return (
      <section className="sf-screen" aria-label="Network Lab" data-testid="network-lab">
        <div className="sf-utility">
          <div className="sf-eyebrow">Read-only network instrument</div>
          <h1>
            NETWORK
            <br />
            LAB.
          </h1>
          <p>No case is open. Network inspection reads records from an active investigation.</p>
          <div className="sf-utility-card">
            <h2>Open a case first</h2>
            <p>
              Pick a past investigation from the Launchpad, or start a new one in the Workbench.
              Observed adapters, IP, DNS, connections, and resolution tests will appear here with
              their tool, source, and collection time.
            </p>
            <button type="button" className="sf-btn sf-btn-lime" onClick={onGoLaunchpad}>
              GO TO LAUNCHPAD ⌂
            </button>
            <button type="button" className="sf-btn sf-btn-dark" onClick={onGoWorkbench}>
              GO TO WORKBENCH ↗
            </button>
          </div>
        </div>
      </section>
    );
  }

  const sections = networkSections(investigation);
  const total = sections.reduce((count, section) => count + section.items.length, 0);
  const banner = targetBanner(investigation.target);
  const refreshing = busyId === "__refresh";

  return (
    <section className="sf-screen" aria-label="Network Lab" data-testid="network-lab">
      <div className="sf-utility">
        <div className="sf-eyebrow">Read-only network instrument</div>
        <h1>
          NETWORK
          <br />
          LAB.
        </h1>
        <p>
          {total} network records on this case · target: {investigation.target}. Only real
          observations are shown — each with its tool, source, and collection time.
        </p>

        <div className="sf-utility-card" data-testid="network-target-banner">
          <h2>{banner.heading}</h2>
          <p>{banner.body}</p>
          <p>
            <button type="button" className="sf-btn sf-btn-dark sf-btn-sm" onClick={onGoEvidence}>
              Full evidence view ↗
            </button>
          </p>
        </div>

        {investigation.target === "local" && (
          <div className="sf-utility-card">
            <h2>Read-only re-checks on this computer</h2>
            <p>
              <label>
                <input
                  type="checkbox"
                  data-testid="network-lab-consent"
                  checked={consented}
                  onChange={(event) => setConsented(event.target.checked)}
                />{" "}
                I consent to run read-only network diagnostics on THIS computer. Each re-check
                re-runs one registered tool call (bounded, timed out, and audit-logged by the
                backend). Nothing here runs arbitrary commands, scans ports, or uploads data.
              </label>
            </p>
          </div>
        )}

        {(error || notice) && (
          <div className="sf-utility-card" aria-live="polite">
            {error && (
              <p role="alert" data-testid="network-lab-error">
                {error}
              </p>
            )}
            {notice && (
              <p role="status" data-testid="network-lab-notice">
                {notice}
              </p>
            )}
            <p>
              <button
                type="button"
                className="sf-btn sf-btn-dark sf-btn-sm"
                data-testid="network-lab-refresh"
                disabled={busyId !== null}
                onClick={() => void refresh()}
              >
                {refreshing ? "Refreshing…" : "Refresh case"}
              </button>{" "}
              {busyId !== null && busyId !== "__refresh" && (
                <button
                  type="button"
                  className="sf-btn sf-btn-dark sf-btn-sm"
                  data-testid="network-lab-cancel"
                  onClick={cancel}
                >
                  Cancel re-check
                </button>
              )}
            </p>
          </div>
        )}
        {!error && !notice && (
          <div className="sf-utility-card">
            <p>
              <button
                type="button"
                className="sf-btn sf-btn-dark sf-btn-sm"
                data-testid="network-lab-refresh"
                disabled={busyId !== null}
                onClick={() => void refresh()}
              >
                {refreshing ? "Refreshing…" : "Refresh case"}
              </button>{" "}
              {busyId !== null && busyId !== "__refresh" && (
                <button
                  type="button"
                  className="sf-btn sf-btn-dark sf-btn-sm"
                  data-testid="network-lab-cancel"
                  onClick={cancel}
                >
                  Cancel re-check
                </button>
              )}
            </p>
          </div>
        )}

        {total === 0 && (
          <div className="sf-utility-card">
            <h2>No network observations yet</h2>
            <p>
              This case holds no adapter, IP, DNS, connection, or resolution records. Continue the
              investigation in the Workbench
              {investigation.target !== "local"
                ? ", or import a Collector package captured on the affected computer."
                : " to collect read-only network evidence."}
            </p>
          </div>
        )}

        {sections.map((section) => (
          <div
            className="sf-utility-card"
            key={section.category}
            data-testid={`network-section-${section.category}`}
          >
            <div className="sf-eyebrow">
              {section.tool} · {section.items.length}{" "}
              {section.items.length === 1 ? "reading" : "readings"}
            </div>
            <h2>{section.title}</h2>
            <p>{section.blurb}</p>
            {section.items.length === 0 ? (
              <p>No {section.title.toLowerCase()} readings on this case.</p>
            ) : (
              section.items
                .slice()
                .reverse()
                .map((item) => {
                  const parsed = parseSource(item.source);
                  return (
                    <div key={item.id} data-testid={`network-item-${item.id}`}>
                      <p>
                        <span className="sf-small-token" title={`Source: ${item.source}`}>
                          {parsed.badge}
                        </span>{" "}
                        <span className="sf-small-token" title="Evidence record id">
                          {item.id}
                        </span>{" "}
                        <span title={`Collected at ${item.collected_at}`}>
                          Last collected: {formatWhen(item.collected_at)}
                        </span>
                      </p>
                      <RecordBody item={item} section={section} />
                      {item.refresh_of && <p>Re-check of {item.refresh_of}.</p>}
                      <RecheckControl
                        item={item}
                        spec={section}
                        target={investigation.target}
                        consented={consented}
                        busy={busyId !== null}
                        onRecheck={() => void recheck(item.id)}
                      />
                      <details>
                        <summary>Raw record data</summary>
                        <pre>{JSON.stringify(item.data, null, 2)}</pre>
                      </details>
                    </div>
                  );
                })
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
