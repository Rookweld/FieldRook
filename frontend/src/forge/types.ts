import type { InvestigationResponse, TurnKind } from "../types";

/**
 * FORGE workstation contracts (EPSILON, new files only).
 *
 * Props-only components: every component receives the full
 * `InvestigationResponse` and returns the full replacement via `onUpdate`,
 * matching the `startInvestigation`/`sendTurn` full-replace pattern in
 * `frontend/src/api.ts`. EPSILON edits no existing file; the lead mounts
 * `WorkspaceShell` in the App.tsx problem tab and wires the actions below.
 */

/** View ids shared with OverviewPanel's InvestigationView (same 4 tabs). */
export type ForgeView = "guide" | "findings" | "evidence" | "resolve";

/** Navigation target: the typed equivalent of OverviewPanel's NextAction. */
export interface ForgeNavigateTarget {
  label: string;
  view: ForgeView;
  focusId?: string;
}

/**
 * Named workstation actions. The lead wires:
 * - "navigate" -> runNextAction({label, view, focusId}) (view + focus move)
 * - "import-collector" -> uploadCollectorPackage(form).then(onUpdate)
 *   (POST FormData file+consent to .../import-collector, full replace)
 */
export type ForgeActionName = "navigate" | "import-collector";

export interface ForgeActionHandler {
  (name: "navigate", target: ForgeNavigateTarget): void;
  (name: "import-collector", form: FormData): void;
}

/** Category -> coverage label. Values mirror OverviewPanel exactly. */
export const FORGE_CATEGORY_LABELS: Record<string, string> = {
  service_status: "Services",
  startup_type: "Services",
  service_details: "Services",
  service_list: "Services",
  event_log: "Event logs",
  app_crashes: "Applications",
  process_info: "Processes",
  os_info: "System",
  net_adapters: "Network",
  ip_config: "Network",
  dns_config: "Network",
  dns_test: "Network",
  connections: "Network",
  scheduled_tasks: "Scheduled tasks",
  demo_worker: "Demo worker",
  error_code: "Error codes",
  screenshot: "Screenshot",
  technician_report: "Technician reports",
};

/* ------------------------------------------------------------------ */
/* forge.knowledge/v1 read-only view types (contract section 1D).      */
/* Case memory and reference docs never merge; these are reference-    */
/* only. Text reaches the model only as quoted excerpts, never as      */
/* system instructions. Components are props-fed; the lead adds        */
/* fetchReferencePassages to api.ts.                                   */
/* ------------------------------------------------------------------ */

/** One retrievable span of vendor/community documentation (~500 chars). */
export interface ReferencePassage {
  doc_id: string;
  title: string;
  path: string;
  anchor: string;
  span: string;
  score: number;
  terms: string[];
}

/** Stable citation handle rendered beside evidence chips. */
export interface ReferenceCitation {
  kind: "reference";
  doc_id: string;
  title: string;
  locator: string;
}

/** Display-only reliability rank (no percentages, contract 1D). */
export type ReferenceReliability =
  | "MEASURED"
  | "TECH_CONFIRMED"
  | "VENDOR_DOC"
  | "COMMUNITY"
  | "INFERRED";

export const RELIABILITY_ORDER: ReferenceReliability[] = [
  "MEASURED",
  "TECH_CONFIRMED",
  "VENDOR_DOC",
  "COMMUNITY",
  "INFERRED",
];

/* ------------------------------------------------------------------ */
/* Props contracts (the Playwright spec is written against these).     */
/* ------------------------------------------------------------------ */

export interface WorkspaceShellProps {
  investigation: InvestigationResponse;
  onUpdate: (inv: InvestigationResponse) => void;
  onEvidenceClick?: (id: string) => void;
  onAction?: ForgeActionHandler;
  onView?: (view: ForgeView) => void;
  onError?: (msg: string) => void;
  disabled?: boolean;
  /** Optional reference strip; absent by default (shell owns the four). */
  references?: ReferencePassage[];
  citations?: ReferenceCitation[];
}

export interface HappeningNowProps {
  investigation: InvestigationResponse;
  onEvidenceClick?: (id: string) => void;
}

export interface DiscoveredRailProps {
  investigation: InvestigationResponse;
  onEvidenceClick?: (id: string) => void;
  /** Opens the Evidence view (shell passes () => onView?.("evidence")). */
  onOpen?: () => void;
}

export interface NextUpQueueProps {
  investigation: InvestigationResponse;
  onAction?: ForgeActionHandler;
  onView?: (view: ForgeView) => void;
}

/** Injectable turn transport; defaults call api.ts (full replace). */
export interface RespondDockTransport {
  sendTurn?: (args: {
    kind: TurnKind;
    text: string;
    questionId: string | null;
    file: File | null;
    consent: boolean;
  }) => Promise<InvestigationResponse>;
  sendFollowup?: (message: string) => Promise<InvestigationResponse>;
  saveNote?: (text: string) => Promise<InvestigationResponse>;
}

export interface RespondDockProps {
  investigation: InvestigationResponse;
  onUpdate: (inv: InvestigationResponse) => void;
  onError?: (msg: string) => void;
  disabled?: boolean;
  transport?: RespondDockTransport;
}

export interface CollectorImportCardProps {
  investigationId: string;
  onAction: ForgeActionHandler;
  onError?: (msg: string) => void;
  disabled?: boolean;
}

export interface IntakeCollectorCardProps {
  /** Receives FormData {file, share_consent}; lead decides ordering. */
  onImport: (form: FormData) => void;
  onError?: (msg: string) => void;
  disabled?: boolean;
}

export interface KnowledgeCiteChipProps {
  citation: ReferenceCitation;
  passage?: ReferencePassage | null;
  onSelect?: (citation: ReferenceCitation) => void;
}
