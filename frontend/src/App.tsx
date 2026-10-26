import { useEffect, useState } from "react";
import { getStatus } from "./api";
import { Header } from "./components/Header";
import { ProblemWorkstation } from "./components/ProblemWorkstation";
import { ServiceWorkstation } from "./components/ServiceWorkstation";
import type { StatusResponse } from "./types";

export function App() {
  const [tab, setTab] = useState<"problem" | "service">("problem");
  const [status, setStatus] = useState<StatusResponse | null>(null);

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
      </nav>
      <main className="main">
        {tab === "problem" ? <ProblemWorkstation /> : <ServiceWorkstation />}
      </main>
      <footer className="footer">
        <span>FieldRook Milestone 002 · Diagnose. Verify. Resolve.</span>
      </footer>
    </div>
  );
}
