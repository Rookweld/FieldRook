import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteKnowledgeEntry,
  fetchKnowledgeMatches,
  fetchReferencePassages,
  listKnowledge,
  recheckKnowledgeEntry,
  recordKnowledge,
  type ReferenceBundle,
} from "../../api";
import type { ReferenceCitation, ReferencePassage } from "../../forge/types";
import type { InvestigationResponse, KnowledgeEntry, KnowledgeMatch } from "../../types";
import { formatApiError } from "./formatError";

export interface KnowledgeQuery {
  q: string;
  category: string;
  outcome: string;
}

/**
 * Knowledge library: filtered list plus delete. Mirrors KnowledgeLibrary
 * (local SQLite only; deleting here never touches live cases).
 */
export function useKnowledgeLibrary(): {
  entries: KnowledgeEntry[];
  loading: boolean;
  error: string | null;
  query: KnowledgeQuery;
  setQuery: (patch: Partial<KnowledgeQuery>) => void;
  refresh: () => void;
  remove: (entryId: string) => Promise<void>;
} {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQueryState] = useState<KnowledgeQuery>({ q: "", category: "", outcome: "" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listKnowledge(query).then(
      (rows) => {
        if (cancelled) return;
        setEntries(rows);
        setLoading(false);
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(formatApiError(e, "Load knowledge"));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [query, nonce]);

  const setQuery = useCallback((patch: Partial<KnowledgeQuery>) => {
    setQueryState((prev) => ({ ...prev, ...patch }));
  }, []);

  const refresh = useCallback(() => {
    setNonce((n) => n + 1);
  }, []);

  const remove = useCallback(async (entryId: string) => {
    setError(null);
    try {
      await deleteKnowledgeEntry(entryId);
      setEntries((prev) => prev.filter((e) => e.entry_id !== entryId));
    } catch (e) {
      setError(formatApiError(e, "Delete knowledge entry"));
    }
  }, []);

  return { entries, loading, error, query, setQuery, refresh, remove };
}

export interface InvestigationKnowledgeBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

/**
 * Per-investigation knowledge: historical matches, reference passages
 * with citations, record-to-memory, and regression rechecks. Matches
 * and references are explicitly loaded (never auto-fetched), matching
 * the M025 WorkedBefore/ProblemWorkstation behaviour.
 */
export function useInvestigationKnowledge(binding: InvestigationKnowledgeBinding): {
  matches: KnowledgeMatch[] | null;
  passages: ReferencePassage[];
  citations: ReferenceCitation[];
  referenceMessage: string;
  busy: string | null;
  error: string | null;
  savedMessage: string | null;
  loadMatches: (limit?: number) => Promise<void>;
  loadReferences: (limit?: number) => Promise<void>;
  recordCause: (confirmedCause: string) => Promise<KnowledgeEntry | null>;
  recheck: (entryId: string) => Promise<void>;
  clearError: () => void;
} {
  const [matches, setMatches] = useState<KnowledgeMatch[] | null>(null);
  const [references, setReferences] = useState<ReferenceBundle>({ passages: [], citations: [], message: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const fail = useCallback((what: string, e: unknown) => {
    const message = formatApiError(e, what);
    setError(message);
    bindingRef.current.onError?.(message);
  }, []);

  const requireId = useCallback((): string | null => {
    const id = bindingRef.current.investigation?.investigation_id ?? null;
    if (!id) fail("Knowledge", new Error("No investigation is open."));
    return id;
  }, [fail]);

  const loadMatches = useCallback(
    async (limit = 5) => {
      const id = requireId();
      if (!id || busyRef.current || bindingRef.current.disabled) return;
      busyRef.current = "matches";
      setBusy("matches");
      setError(null);
      try {
        const bundle = await fetchKnowledgeMatches(id, limit);
        setMatches(bundle.matches);
      } catch (e) {
        fail("Load knowledge matches", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail, requireId],
  );

  const loadReferences = useCallback(
    async (limit = 5) => {
      const id = requireId();
      if (!id || busyRef.current || bindingRef.current.disabled) return;
      busyRef.current = "references";
      setBusy("references");
      setError(null);
      try {
        setReferences(await fetchReferencePassages(id, limit));
      } catch (e) {
        fail("Load references", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail, requireId],
  );

  const recordCause = useCallback(
    async (confirmedCause: string) => {
      const id = requireId();
      if (!id || busyRef.current || bindingRef.current.disabled) return null;
      busyRef.current = "record";
      setBusy("record");
      setError(null);
      setSavedMessage(null);
      try {
        const entry = await recordKnowledge(id, confirmedCause);
        setSavedMessage(
          `Saved as ${entry.entry_id} (${entry.outcome}, ${entry.occurrence_count} occurrence${entry.occurrence_count === 1 ? "" : "s"}).`,
        );
        return entry;
      } catch (e) {
        fail("Record knowledge", e);
        return null;
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail, requireId],
  );

  const recheck = useCallback(
    async (entryId: string) => {
      const id = requireId();
      if (!id || busyRef.current || bindingRef.current.disabled) return;
      busyRef.current = `recheck-${entryId}`;
      setBusy(busyRef.current);
      setError(null);
      try {
        bindingRef.current.onUpdate(await recheckKnowledgeEntry(id, entryId));
      } catch (e) {
        fail("Recheck knowledge entry", e);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [fail, requireId],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    matches,
    passages: references.passages,
    citations: references.citations,
    referenceMessage: references.message,
    busy,
    error,
    savedMessage,
    loadMatches,
    loadReferences,
    recordCause,
    recheck,
    clearError,
  };
}
