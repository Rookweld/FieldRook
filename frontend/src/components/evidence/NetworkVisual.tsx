import type { EvidenceItem } from "../../types";
import { EmptyState } from "../EmptyState";
import { arr, fmt, obj, SectionTitle, SliceNote, str } from "./shared";

function DnsTest({ item }: { item: EvidenceItem }) {
  const d = item.data;
  const host = str(d["hostname"]) ?? "(unknown host)";
  const ok = d["succeeded"];
  const addresses = arr(d["addresses"]).filter((a) => str(a) !== null) as string[];
  const ms = d["query_ms"];
  return (
    <div className="net">
      <div className="net-verdict">
        <code className="mono net-host">{host}</code>
        {ok === true ? (
          <span className="verdict verdict-pass">RESOLVES</span>
        ) : ok === false ? (
          <span className="verdict verdict-unavailable">NO RESOLUTION</span>
        ) : (
          <span className="verdict verdict-changed">UNKNOWN</span>
        )}
      </div>
      {addresses.length > 0 && (
        <ul className="chip-list">
          {addresses.slice(0, 6).map((a) => (
            <li key={a}>
              <code className="chip mono">{a}</code>
            </li>
          ))}
        </ul>
      )}
      <dl className="fact-grid">
        {ms !== null && ms !== undefined && (
          <div className="fact">
            <dt>Query time</dt>
            <dd className="mono">{fmt(ms)} ms</dd>
          </div>
        )}
        {str(d["error"]) && (
          <div className="fact">
            <dt>Detail</dt>
            <dd>{str(d["error"])}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function DnsConfig({ item }: { item: EvidenceItem }) {
  const ifaces = arr(item.data["interfaces"]).map(obj).filter((o) => o !== null);
  return (
    <div className="net">
      {str(item.data["summary"]) && <p className="muted">{str(item.data["summary"])}</p>}
      {ifaces.length === 0 && (
        <EmptyState
          icon="◇"
          title="No interface DNS data"
          body="The collector returned no per-interface name servers for this reading."
        />
      )}
      {ifaces.slice(0, 4).map((iface, i) => {
        const servers = arr(iface["servers"]).filter((s) => str(s) !== null) as string[];
        return (
          <div key={`${str(iface["interface"]) ?? i}`} className="net-iface">
            <p className="net-iface-name">{str(iface["interface"]) ?? "Interface"}</p>
            {servers.length > 0 ? (
              <ul className="chip-list">
                {servers.map((s) => (
                  <li key={s}>
                    <code className="chip mono">{s}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">(no servers)</p>
            )}
          </div>
        );
      })}
      <SliceNote shown={Math.min(ifaces.length, 4)} total={ifaces.length} what="interfaces" />
    </div>
  );
}

function Adapters({ item }: { item: EvidenceItem }) {
  const d = item.data;
  const adapters = arr(d["adapters"]);
  const addresses = arr(d["addresses"] ?? d["ip_addresses"] ?? []);
  const conns = arr(d["connections"]).map(obj).filter((o) => o !== null);
  return (
    <div className="net">
      {str(d["summary"]) && <p className="muted">{str(d["summary"])}</p>}
      {adapters.length > 0 && (
        <>
          <SectionTitle>Adapters ({adapters.length})</SectionTitle>
          <ul className="net-rows">
            {adapters.slice(0, 6).map((a, i) => {
              const o = obj(a);
              return (
                <li key={i}>
                  <code className="mono">{o ? (str(o["name"]) ?? str(o["description"]) ?? fmt(a)) : fmt(a)}</code>
                  {o && str(o["status"]) && <span className="muted">{str(o["status"])}</span>}
                  {o && str(o["mac"]) && <span className="mono muted">{str(o["mac"])}</span>}
                </li>
              );
            })}
          </ul>
          <SliceNote shown={Math.min(adapters.length, 6)} total={adapters.length} what="adapters" />
        </>
      )}
      {addresses.length > 0 && (
        <>
          <SectionTitle>Addresses</SectionTitle>
          <ul className="net-rows">
            {addresses.slice(0, 8).map((a, i) => {
              const o = obj(a);
              const ip = o ? str(o["ip_address"]) : null;
              const prefix = o ? str(o["prefix_length"]) : null;
              return (
                <li key={i}>
                  <code className="mono">
                    {ip ?? fmt(a)}
                    {ip && prefix ? `/${prefix}` : ""}
                  </code>
                  {o && str(o["interface"]) && <span className="muted">{str(o["interface"])}</span>}
                  {o && str(o["address_family"]) && (
                    <span className="mono muted">{str(o["address_family"])}</span>
                  )}
                  {o && str(o["prefix_origin"]) && (
                    <span className="muted">{str(o["prefix_origin"])}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
      {conns.length > 0 && (
        <>
          <SectionTitle>Connection sample ({conns.length})</SectionTitle>
          <ul className="net-rows">
            {conns.slice(0, 5).map((c, i) => (
              <li key={i}>
                <code className="mono">{str(c["local"]) ?? "?"}</code>
                <span aria-hidden="true">→</span>
                <code className="mono">{str(c["remote"]) ?? "?"}</code>
                {str(c["state"]) && <span className="muted">{str(c["state"])}</span>}
              </li>
            ))}
          </ul>
          <SliceNote shown={Math.min(conns.length, 5)} total={conns.length} what="connections" />
        </>
      )}
    </div>
  );
}

export function NetworkVisual({ item }: { item: EvidenceItem }) {
  if (item.category === "dns_test") return <DnsTest item={item} />;
  if (item.category === "dns_config") return <DnsConfig item={item} />;
  return <Adapters item={item} />;
}
