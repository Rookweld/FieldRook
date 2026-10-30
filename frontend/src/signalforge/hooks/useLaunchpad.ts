import { useCallback, useEffect, useState } from "react";
import { getDesktopStatus, listInvestigations, type DesktopStatusResponse } from "../../api";
import type { InvestigationSummary } from "../../types";
import { formatApiError } from "./formatError";

/**
 * Launchpad data: backend identity/status plus real recent cases.
 * Recents come from the same persisted store as History; nothing here
 * is invented. Status carries the desktop-identity runtime field.
 */
export function useLaunchpad(limit = 10): {
  status: DesktopStatusResponse | null;
  recents: InvestigationSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const [status, setStatus] = useState<DesktopStatusResponse | null>(null);
  const [recents, setRecents] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getDesktopStatus(), listInvestigations(limit)]).then(
      ([st, rows]) => {
        if (cancelled) return;
        setStatus(st);
        setRecents(rows);
        setLoading(false);
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(formatApiError(e, "Launchpad load"));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [limit, nonce]);

  const refresh = useCallback(() => {
    setNonce((n) => n + 1);
  }, []);

  return { status, recents, loading, error, refresh };
}
