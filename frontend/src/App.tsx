import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getInvestigation, getStatus, listInvestigations } from "./api";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ProblemWorkstation } from "./components/ProblemWorkstation";
import { FirstRunGate } from "./forge/FirstRunGate";
import type { InvestigationResponse, InvestigationSummary, StatusResponse } from "./types";
import { SignalFrame } from "./signalforge/components/Shell";
import { Launchpad } from "./signalforge/views/Launchpad";
import { Workbench } from "./signalforge/views/Workbench";
import { EvidenceView } from "./signalforge/views/EvidenceView";
import { KnowledgeView } from "./signalforge/views/KnowledgeView";
import { SettingsView } from "./signalforge/views/SettingsView";
import type { Route, SignalView } from "./signalforge/types";
import "./signalforge/tokens.css";

export function App() {
  // M026 navigation replaces the M025 four-tab model. Workbench first:
  // matches the Motion Lab default and keeps the intake-first flow.
  const [route, setRoute] = useState<Route>({ view: "workbench" });
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [recents, setRecents] = useState<InvestigationSummary[]>([]);
  const [recentsLoading, setRecentsLoading] = useState(true);
  const [recentsError, setRecentsError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [seeded, setSeeded] = useState<InvestigationResponse | null>(null);
  // Live mirror of the engine's investigation (ProblemWorkstation notifies
  // up; App never fetches or mutates it). Drives the hero, rail, Evidence.
  const [mirror, setMirror] = useState<InvestigationResponse | null>(null);
  // Bumps to remount the engine for a guaranteed-fresh intake.
  const [session, setSession] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Ambient tint for non-workbench views; the engine owns data-view while
  // it is mounted (same split as the M025 tab model).
  useEffect(() => {
    if (route.view !== "workbench") {
      document.querySelector(".app")?.setAttribute("data-view", route.view);
    }
  }, [route.view]);

  useEffect(() => {
    let cancelled = false;
    getStatus().then(
      (st) => {
        if (!cancelled) setStatus(st);
      },
      () => {
        /* badges show "connecting" until the backend answers */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshRecents = useCallback(async (): Promise<void> => {
    setRecentsLoading(true);
    setRecentsError(null);
    try {
      const rows = await listInvestigations();
      if (!mounted.current) return;
      setRecents(rows);
    } catch (e: unknown) {
      if (!mounted.current) return;
      setRecentsError(
        e instanceof ApiError
          ? `Recent investigations failed (HTTP ${e.status}): ${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      if (mounted.current) setRecentsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshRecents();
  }, [refreshRecents]);

  useEffect(() => {
    if (route.view === "launchpad") void refreshRecents();
  }, [route.view, refreshRecents]);

  const navigate = useCallback((view: SignalView) => {
    setNotice(null);
    setRoute((prev) => ({ ...prev, view }));
    document.getElementById("sf-main")?.scrollTo({ top: 0 });
  }, []);

  const handleMirror = useCallback((inv: InvestigationResponse | null) => {
    setMirror(inv);
  }, []);

  const openInvestigation = useCallback(
    async (id: string): Promise<void> => {
      if (openingId !== null) return;
      setOpeningId(id);
      setNotice(null);
      try {
        const inv = await getInvestigation(id);
        if (!mounted.current) return;
        setSeeded(inv);
        setMirror(inv);
        setSession((s) => s + 1);
        setRoute({ view: "workbench", investigationId: inv.investigation_id });
        void refreshRecents();
      } catch (e: unknown) {
        if (!mounted.current) return;
        setNotice(
          e instanceof ApiError
            ? `Open failed (HTTP ${e.status}): ${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (mounted.current) setOpeningId(null);
      }
    },
    [openingId, refreshRecents],
  );

  const startNew = useCallback(() => {
    setNotice(null);
    setSeeded(null);
    setMirror(null);
    setSession((s) => s + 1);
    setRoute({ view: "workbench" });
  }, []);

  /** Real import, via the consented engine surface (intake or workspace). */
  const goImport = useCallback(() => {
    setNotice(null);
    setRoute((prev) => ({ ...prev, view: "workbench" }));
    window.setTimeout(() => {
      const host = document.querySelector(
        '[data-testid="forge-intake-collector"], [data-testid="forge-collector-import"]',
      );
      host?.scrollIntoView({ block: "center" });
      host?.querySelector<HTMLInputElement>('input[type="file"]')?.focus({ preventScroll: true });
    }, 80);
  }, []);

  /** Interim quick-capture: jump to the engine's real notes box. */
  const goNotes = useCallback((_draft: string) => {
    setRoute((prev) => ({ ...prev, view: "workbench" }));
    window.setTimeout(() => {
      const el =
        document.getElementById("sf-engine-note") ?? document.getElementById("sf-engine-problem");
      el?.scrollIntoView({ block: "center" });
      el?.focus({ preventScroll: true });
    }, 80);
  }, []);

  const openGuide = useCallback(() => {
    setRoute((prev) => ({ ...prev, view: "workbench" }));
    window.setTimeout(() => {
      const el =
        document.getElementById("sf-engine-tab-guide") ??
        document.getElementById("sf-engine-problem");
      el?.scrollIntoView({ block: "center" });
      el?.focus({ preventScroll: true });
    }, 80);
  }, []);

  return (
    <SignalFrame
      view={route.view}
      status={status}
      investigation={mirror}
      onNavigate={navigate}
      onGoEvidence={() => navigate("evidence")}
      onGoWorkbench={() => navigate("workbench")}
    >
      <FirstRunGate />
      <ErrorBoundary
        key={`${route.view}:${route.investigationId ?? "none"}:${session}`}
        onReset={() => {
          setSeeded(null);
          setMirror(null);
          setRoute({ view: "workbench" });
        }}
      >
        {route.view === "launchpad" && (
          <Launchpad
            status={status}
            recents={recents}
            recentsLoading={recentsLoading}
            recentsError={recentsError}
            notice={notice}
            openingId={openingId}
            onNew={startNew}
            onImport={goImport}
            onOpen={(id) => void openInvestigation(id)}
            onRetryRecents={() => void refreshRecents()}
          />
        )}
        {route.view === "workbench" && (
          <Workbench
            investigation={mirror}
            status={status}
            onNew={startNew}
            onImport={goImport}
            onGoNotes={goNotes}
            onGoEvidence={() => navigate("evidence")}
            onGoLaunchpad={() => navigate("launchpad")}
            onOpenGuide={openGuide}
          >
            <ProblemWorkstation
              key={`${seeded?.investigation_id ?? "new"}:${session}`}
              initial={seeded}
              onInvestigationChange={handleMirror}
            />
          </Workbench>
        )}
        {route.view === "evidence" && (
          <EvidenceView
            investigation={mirror}
            onGoWorkbench={() => navigate("workbench")}
            onGoLaunchpad={() => navigate("launchpad")}
          />
        )}
        {route.view === "knowledge" && <KnowledgeView />}
        {route.view === "settings" && <SettingsView status={status} investigation={mirror} />}
      </ErrorBoundary>
    </SignalFrame>
  );
}
