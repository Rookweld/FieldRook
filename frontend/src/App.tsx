import { useEffect, useState } from "react";
import { getStatus } from "./api";
import { Header } from "./components/Header";
import { History } from "./components/History";
import { ProblemWorkstation } from "./components/ProblemWorkstation";
import { ServiceWorkstation } from "./components/ServiceWorkstation";
import type { InvestigationResponse, StatusResponse } from "./types";

export function App() {
  const [tab, setTab] = useState<"problem" | "service" | "history">("problem");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [seeded, setSeeded] = useState<InvestigationResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStatus().then(
      (st) => {
        if (!cancelled) setStatus(st);
      },
      () => {
        /* header shows "connecting" until the backend answers */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <Header status={status} />
      <nav className="tabs" aria-label="Workstation">
        <button
          type="button"
          className={tab === "problem" ? "tab tab-active" : "tab"}
          onClick={() => setTab("problem")}
        >
          Investigate problem
        </button>
        <button
          type="button"
          className={tab === "service" ? "tab tab-active" : "tab"}
          onClick={() => setTab("service")}
        >
          Service lookup
        </button>
        <button
          type="button"
          className={tab === "history" ? "tab tab-active" : "tab"}
          onClick={() => setTab("history")}
        >
          History
        </button>
      </nav>
      <main className="main">
        {tab === "problem" ? (
          <ProblemWorkstation
            key={seeded?.investigation_id ?? "new"}
            initial={seeded}
          />
        ) : tab === "service" ? (
          <ServiceWorkstation />
        ) : (
          <History
            onOpen={(inv) => {
              setSeeded(inv);
              setTab("problem");
            }}
          />
        )}
      </main>
      <footer className="footer">
        <span>FieldRook Milestone 004 · Diagnose. Verify. Resolve.</span>
      </footer>
    </div>
  );
}
