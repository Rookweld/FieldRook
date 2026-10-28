import { useEffect, useState } from "react";
import { getStatus } from "./api";
import { Atmosphere } from "./components/Atmosphere";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Header } from "./components/Header";
import { History } from "./components/History";
import { KnowledgeLibrary } from "./components/KnowledgeLibrary";
import { ProblemWorkstation } from "./components/ProblemWorkstation";
import { ServiceWorkstation } from "./components/ServiceWorkstation";
import type { InvestigationResponse, StatusResponse } from "./types";

export function App() {
  const [tab, setTab] = useState<"problem" | "service" | "history" | "knowledge">("problem");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [seeded, setSeeded] = useState<InvestigationResponse | null>(null);

  // Ambient tint for the library tabs; the problem workstation owns
  // data-view while it is mounted.
  useEffect(() => {
    if (tab !== "problem") {
      document.querySelector(".app")?.setAttribute("data-view", tab);
    }
  }, [tab]);

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
      <Atmosphere />
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
        <button
          type="button"
          className={tab === "knowledge" ? "tab tab-active" : "tab"}
          onClick={() => setTab("knowledge")}
        >
          Knowledge
        </button>
      </nav>
      <main className="main">
        <ErrorBoundary
          key={tab}
          onReset={() => {
            setSeeded(null);
            setTab("problem");
          }}
        >
          {tab === "problem" ? (
            <ProblemWorkstation
              key={seeded?.investigation_id ?? "new"}
              initial={seeded}
            />
          ) : tab === "service" ? (
            <ServiceWorkstation />
          ) : tab === "knowledge" ? (
            <KnowledgeLibrary />
          ) : (
            <History
              onOpen={(inv) => {
                setSeeded(inv);
                setTab("problem");
              }}
            />
          )}
        </ErrorBoundary>
      </main>
      <footer className="footer">
        <span>FieldRook Milestone 017 · Diagnose. Verify. Resolve.</span>
      </footer>
    </div>
  );
}
