/**
 * Wiring contract check (GAMMA). Not imported by any view: `tsc --noEmit`
 * (the frontend gate) type-checks every hook signature, binding shape,
 * and api.ts extension below, so a drifted contract fails the build
 * instead of failing at integration. Returns are `void`ed; nothing here
 * runs in the product (vite bundles only imported modules).
 */
import {
  fetchInvestigationExport,
  fetchKnowledgeExport,
  getDesktopStatus,
  investigationExportUrl,
  knowledgeExportUrl,
  listInvestigations,
  type DesktopStatusResponse,
  type ExportFormat,
} from "../../api";
import type { InvestigationResponse } from "../../types";
import { useActions } from "./useActions";
import { useCollectorImport } from "./useCollectorImport";
import { useExport } from "./useExport";
import { useGuidedChecks } from "./useGuidedChecks";
import { useInvestigation } from "./useInvestigation";
import { useInvestigationKnowledge, useKnowledgeLibrary } from "./useKnowledge";
import { useLaunchpad } from "./useLaunchpad";
import { useProviders } from "./useProviders";
import { useResolution } from "./useResolution";
import { useServices } from "./useServices";
import { useTools } from "./useTools";
import { useViewState, type SignalforgeView } from "./useViewState";
import { isShellBridgeAvailable, ShellBridgeError } from "../shellBridge";

function noopUpdate(_next: InvestigationResponse): void {
  /* contract placeholder */
}

export function ContractViewState(): null {
  const nav = useViewState();
  const view: SignalforgeView = nav.state.view;
  void view;
  const id: string | null = nav.state.investigationId;
  void id;
  nav.go("workbench");
  nav.openInvestigation("inv-1");
  nav.startNew();
  nav.reset();
  return null;
}

export function ContractLaunchpad(): null {
  const pad = useLaunchpad(5);
  const status: DesktopStatusResponse | null = pad.status;
  void status;
  void pad.recents.length;
  void pad.loading;
  pad.refresh();
  return null;
}

export function ContractInvestigation(): null {
  const inv = useInvestigation({ initial: null, onError: noopMessage });
  void inv.investigation;
  void inv.busy;
  void inv.error;
  void inv.start({ problem: "p", shareConsent: true });
  void inv.open("inv-1");
  void inv.refresh();
  void inv.send({ kind: "answer", text: "t", shareConsent: true });
  void inv.followUp("m");
  void inv.addNote("n");
  void inv.cancel();
  void inv.reverify("ev-1");
  inv.clearError();
  return null;
}

function noopMessage(_message: string): void {
  /* contract placeholder */
}

export function ContractGuidedChecks(): null {
  const checks = useGuidedChecks({ investigation: null, onUpdate: noopUpdate });
  void checks.busy;
  void checks.completeStep("s", "o");
  void checks.markImpossible("s", "r");
  void checks.setHypothesis("h", "confirmed", "r");
  void checks.setTargetValue("remote");
  checks.clearError();
  return null;
}

export function ContractProviders(): null {
  const providers = useProviders({ investigation: null, onUpdate: noopUpdate });
  void providers.providers.length;
  void providers.loading;
  void providers.localResult;
  providers.refresh();
  void providers.testLocal();
  void providers.switchTo("simulated", false);
  providers.clearError();
  return null;
}

export function ContractServices(): null {
  const svc = useServices();
  void svc.services.length;
  void svc.mode;
  svc.select("wuauserv");
  void svc.loadDiagnostics(true);
  void svc.analyze(false);
  void svc.diagnostics;
  void svc.assessment;
  svc.clearError();
  return null;
}

export function ContractTools(): null {
  const tools = useTools();
  void tools.tools.length;
  tools.refresh();
  return null;
}

export function ContractActions(): null {
  const actions = useActions({ investigation: null, onUpdate: noopUpdate });
  void actions.approvedIds.length;
  void actions.propose("a", "t", "r");
  void actions.approve("p");
  void actions.reject("p");
  void actions.execute("p");
  actions.clearError();
  return null;
}

export function ContractResolution(): null {
  const resolution = useResolution({ investigation: null, onUpdate: noopUpdate });
  void resolution.template;
  void resolution.loadTemplate("a");
  void resolution.create({
    evidence_ids: [],
    intended_state: "s",
    criteria: [],
    guidance: "g",
    risks: "r",
    remediation_kind: "manual",
  });
  void resolution.baseline("p");
  void resolution.recordManual("p", "d");
  void resolution.linkExecution("p", "e");
  void resolution.verify("p");
  resolution.clearError();
  return null;
}

export function ContractCollectorImport(): null {
  const importer = useCollectorImport({ investigationId: null, onUpdate: noopUpdate });
  void importer.busy;
  void importer.importFile(null, true);
  void importer.importShellFile({ path: "p", name: "n.zip", sizeBytes: 1, contentBase64: null }, true);
  importer.clearError();
  return null;
}

export function ContractKnowledge(): null {
  const library = useKnowledgeLibrary();
  void library.entries.length;
  library.setQuery({ q: "dns" });
  library.refresh();
  void library.remove("e");
  const detail = useInvestigationKnowledge({ investigation: null, onUpdate: noopUpdate });
  void detail.matches;
  void detail.passages.length;
  void detail.citations.length;
  void detail.referenceMessage;
  void detail.loadMatches(3);
  void detail.loadReferences(3);
  void detail.recordCause("cause");
  void detail.recheck("e");
  void detail.savedMessage;
  detail.clearError();
  return null;
}

export function ContractExport(): null {
  const exporter = useExport();
  const format: ExportFormat = "markdown";
  const url: string = exporter.investigationUrl("inv-1", format);
  void url;
  void exporter.knowledgeUrl("e", "json");
  void exporter.downloadInvestigation("inv-1", "json");
  void exporter.downloadKnowledge("e", "markdown");
  exporter.clearError();
  return null;
}

export function ContractApiExtensions(): null {
  void getDesktopStatus().then((status) => {
    const runtime: string = status.runtime;
    void runtime;
  });
  const url: string = investigationExportUrl("inv-1", "json");
  void url;
  void knowledgeExportUrl("e", "markdown");
  void fetchInvestigationExport("inv-1", "markdown").then((text: string) => text.length);
  void fetchKnowledgeExport("e", "json").then((text: string) => text.length);
  void listInvestigations(5);
  return null;
}

export function ContractShellBridge(): null {
  const available: boolean = isShellBridgeAvailable();
  void available;
  const error = new ShellBridgeError("unavailable", "no bridge");
  void error.code;
  return null;
}
