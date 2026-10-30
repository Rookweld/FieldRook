import { useCallback, useEffect, useState } from "react";
import { analyzeIncident, getDiagnostics, listServices } from "../../api";
import type { DiagnosticBundle, IncidentAssessment, ServiceSummary } from "../../types";
import { formatApiError } from "./formatError";

/**
 * M025 service lookup, preserved: list services, pull diagnostics for
 * one service, and run an incident analysis. Mirrors ServiceWorkstation
 * boot (prefers wuauserv when present, else the first service).
 */
export function useServices(): {
  services: ServiceSummary[];
  mode: string;
  selected: string;
  diagnostics: DiagnosticBundle | null;
  assessment: IncidentAssessment | null;
  loading: boolean;
  busy: "diagnostics" | "analyze" | null;
  error: string | null;
  select: (name: string) => void;
  loadDiagnostics: (useFixtures?: boolean) => Promise<void>;
  analyze: (useFixtures?: boolean) => Promise<void>;
  clearError: () => void;
} {
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [mode, setMode] = useState("…");
  const [selected, setSelected] = useState("");
  const [diagnostics, setDiagnostics] = useState<DiagnosticBundle | null>(null);
  const [assessment, setAssessment] = useState<IncidentAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"diagnostics" | "analyze" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listServices().then(
      (svc) => {
        if (cancelled) return;
        setServices(svc.services);
        setMode(svc.mode);
        setSelected(
          svc.services.some((s) => s.name === "wuauserv") ? "wuauserv" : (svc.services[0]?.name ?? ""),
        );
        setLoading(false);
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(formatApiError(e, "Load services"));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const select = useCallback((name: string) => {
    setSelected(name);
    setDiagnostics(null);
    setAssessment(null);
  }, []);

  const loadDiagnostics = useCallback(
    async (useFixtures?: boolean) => {
      if (!selected || busy) return;
      setBusy("diagnostics");
      setError(null);
      try {
        setDiagnostics(await getDiagnostics(selected, useFixtures));
      } catch (e) {
        setError(formatApiError(e, "Load diagnostics"));
      } finally {
        setBusy(null);
      }
    },
    [busy, selected],
  );

  const analyze = useCallback(
    async (useFixtures?: boolean) => {
      if (!selected || busy) return;
      setBusy("analyze");
      setError(null);
      try {
        setAssessment(await analyzeIncident(selected, useFixtures));
      } catch (e) {
        setError(formatApiError(e, "Analyze incident"));
      } finally {
        setBusy(null);
      }
    },
    [busy, selected],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    services,
    mode,
    selected,
    diagnostics,
    assessment,
    loading,
    busy,
    error,
    select,
    loadDiagnostics,
    analyze,
    clearError,
  };
}
