import { useCallback, useEffect, useState } from "react";
import { listTools } from "../../api";
import type { ToolInfo } from "../../types";
import { formatApiError } from "./formatError";

/** Registered diagnostic tool catalogue (read-only reference data). */
export function useTools(): {
  tools: ToolInfo[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listTools().then(
      (rows) => {
        if (cancelled) return;
        setTools(rows);
        setLoading(false);
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(formatApiError(e, "Load tools"));
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

  return { tools, loading, error, refresh };
}
