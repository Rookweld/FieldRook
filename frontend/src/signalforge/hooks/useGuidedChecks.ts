import { useCallback, useRef, useState } from "react";
import {
  completePlanStep,
  impossiblePlanStep,
  setHypothesisStatus,
  setTarget,
} from "../../api";
import type { DiagnosisTarget, InvestigationResponse } from "../../types";
import { formatApiError } from "./formatError";

export interface GuidedChecksBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

/**
 * Guided troubleshooting checks: plan-step outcomes, hypothesis status,
 * and diagnostic target. Mirrors GuidePanel semantics exactly (full
 * replace via onUpdate); no-ops honestly when nothing is open.
 */
export function useGuidedChecks(binding: GuidedChecksBinding): {
  busy: string | null;
  error: string | null;
  completeStep: (stepId: string, outcome: string) => Promise<void>;
  markImpossible: (stepId: string, reason: string) => Promise<void>;
  setHypothesis: (hypothesisId: string, status: string, reason: string) => Promise<void>;
  setTargetValue: (target: DiagnosisTarget) => Promise<void>;
  clearError: () => void;
} {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const run = useCallback(async (key: string, what: string, fn: (id: string) => Promise<InvestigationResponse>) => {
    const { investigation, onUpdate, onError, disabled } = bindingRef.current;
    if (disabled || busyRef.current) return;
    if (!investigation) {
      const message = "No investigation is open.";
      setError(message);
      onError?.(message);
      return;
    }
    busyRef.current = true;
    setBusy(key);
    setError(null);
    try {
      onUpdate(await fn(investigation.investigation_id));
    } catch (e) {
      const message = formatApiError(e, what);
      setError(message);
      onError?.(message);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }, []);

  const completeStep = useCallback(
    (stepId: string, outcome: string) =>
      run("complete-step", "Complete plan step", (id) => completePlanStep(id, stepId, outcome)),
    [run],
  );

  const markImpossible = useCallback(
    (stepId: string, reason: string) =>
      run("impossible-step", "Mark step impossible", (id) => impossiblePlanStep(id, stepId, reason)),
    [run],
  );

  const setHypothesis = useCallback(
    (hypothesisId: string, status: string, reason: string) =>
      run("hypothesis", "Update hypothesis", (id) =>
        setHypothesisStatus(id, hypothesisId, status, reason),
      ),
    [run],
  );

  const setTargetValue = useCallback(
    (target: DiagnosisTarget) => run("target", "Set diagnostic target", (id) => setTarget(id, target)),
    [run],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { busy, error, completeStep, markImpossible, setHypothesis, setTargetValue, clearError };
}
