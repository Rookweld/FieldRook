import { useCallback, useEffect, useRef, useState } from "react";
import { listProviders, switchProvider, testLocalProvider } from "../../api";
import type { InvestigationResponse, LocalTestResult, ProviderOption } from "../../types";
import { formatApiError } from "./formatError";

export interface ProvidersBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

/**
 * Provider selection: list options, probe the local model, and switch
 * the open investigation's provider (cloud switches need explicit
 * confirmCloud, exactly as GuidePanel requires).
 */
export function useProviders(binding: ProvidersBinding): {
  providers: ProviderOption[];
  loading: boolean;
  testing: boolean;
  busy: boolean;
  error: string | null;
  localResult: LocalTestResult | null;
  refresh: () => void;
  testLocal: () => Promise<void>;
  switchTo: (provider: string, confirmCloud: boolean) => Promise<void>;
  clearError: () => void;
} {
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localResult, setLocalResult] = useState<LocalTestResult | null>(null);
  const [nonce, setNonce] = useState(0);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listProviders().then(
      (rows) => {
        if (cancelled) return;
        setProviders(rows);
        setLoading(false);
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(formatApiError(e, "Load providers"));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  const refresh = useCallback(() => {
    setNonce((n) => n + 1);
  }, []);

  const testLocal = useCallback(async () => {
    if (testing) return;
    setTesting(true);
    setError(null);
    try {
      setLocalResult(await testLocalProvider());
    } catch (e) {
      const message = formatApiError(e, "Test local provider");
      setError(message);
      bindingRef.current.onError?.(message);
    } finally {
      setTesting(false);
    }
  }, [testing]);

  const switchTo = useCallback(async (provider: string, confirmCloud: boolean) => {
    const { investigation, onUpdate, onError, disabled } = bindingRef.current;
    if (disabled || busy) return;
    if (!investigation) {
      const message = "No investigation is open.";
      setError(message);
      onError?.(message);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onUpdate(await switchProvider(investigation.investigation_id, provider, confirmCloud));
    } catch (e) {
      const message = formatApiError(e, "Switch provider");
      setError(message);
      onError?.(message);
    } finally {
      setBusy(false);
    }
  }, [busy]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { providers, loading, testing, busy, error, localResult, refresh, testLocal, switchTo, clearError };
}
