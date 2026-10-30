import { useCallback, useRef, useState } from "react";
import {
  captureBaseline,
  createPlan,
  getPlanTemplate,
  linkPlanExecution,
  recordManualIntervention,
  verifyPlan,
  type CriterionDraft,
} from "../../api";
import type { InvestigationResponse, PlanTemplate } from "../../types";
import { formatApiError } from "./formatError";

export interface ResolutionBinding {
  investigation: InvestigationResponse | null;
  onUpdate: (next: InvestigationResponse) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

export interface ResolutionCreateInput {
  evidence_ids: string[];
  intended_state: string;
  criteria: CriterionDraft[];
  guidance: string;
  risks: string;
  remediation_kind: "manual" | "action";
  action_id?: string;
  target?: string;
}

/**
 * Resolution plans: template -> create -> baseline -> intervene (manual
 * claim or linked authorized execution) -> verify. Every step returns
 * the full investigation and replaces state (mirrors ResolutionWorkspace).
 */
export function useResolution(binding: ResolutionBinding): {
  busy: string | null;
  error: string | null;
  template: PlanTemplate | null;
  loadTemplate: (actionId: string) => Promise<void>;
  create: (input: ResolutionCreateInput) => Promise<void>;
  baseline: (planId: string) => Promise<void>;
  recordManual: (planId: string, description: string) => Promise<void>;
  linkExecution: (planId: string, executionId: string) => Promise<void>;
  verify: (planId: string) => Promise<void>;
  clearError: () => void;
} {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [template, setTemplate] = useState<PlanTemplate | null>(null);
  const busyRef = useRef<string | null>(null);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;

  const runOnPlan = useCallback(
    async (key: string, what: string, fn: () => Promise<InvestigationResponse>) => {
      const { onUpdate, onError, disabled } = bindingRef.current;
      if (disabled || busyRef.current) return;
      busyRef.current = key;
      setBusy(key);
      setError(null);
      try {
        onUpdate(await fn());
      } catch (e) {
        const message = formatApiError(e, what);
        setError(message);
        onError?.(message);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [],
  );

  const loadTemplate = useCallback(
    async (actionId: string) => {
      if (bindingRef.current.disabled || busyRef.current) return;
      busyRef.current = "template";
      setBusy("template");
      setError(null);
      try {
        setTemplate(await getPlanTemplate(actionId));
      } catch (e) {
        const message = formatApiError(e, "Load plan template");
        setError(message);
        bindingRef.current.onError?.(message);
      } finally {
        busyRef.current = null;
        setBusy(null);
      }
    },
    [],
  );

  const create = useCallback(
    async (input: ResolutionCreateInput) => {
      const { investigation, onError } = bindingRef.current;
      if (!investigation) {
        const message = "No investigation is open.";
        setError(message);
        onError?.(message);
        return;
      }
      const investigationId = investigation.investigation_id;
      await runOnPlan("create", "Create resolution plan", () =>
        createPlan({ ...input, investigationId }),
      );
    },
    [runOnPlan],
  );

  const baseline = useCallback(
    (planId: string) => runOnPlan(`baseline-${planId}`, "Capture baseline", () => captureBaseline(planId)),
    [runOnPlan],
  );

  const recordManual = useCallback(
    (planId: string, description: string) =>
      runOnPlan(`manual-${planId}`, "Record manual intervention", () =>
        recordManualIntervention(planId, description),
      ),
    [runOnPlan],
  );

  const linkExecution = useCallback(
    (planId: string, executionId: string) =>
      runOnPlan(`link-${planId}`, "Link plan execution", () => linkPlanExecution(planId, executionId)),
    [runOnPlan],
  );

  const verify = useCallback(
    (planId: string) => runOnPlan(`verify-${planId}`, "Verify plan", () => verifyPlan(planId)),
    [runOnPlan],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { busy, error, template, loadTemplate, create, baseline, recordManual, linkExecution, verify, clearError };
}
