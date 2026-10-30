import type {
  InvestigationResponse,
  InvestigationSummary,
  StatusResponse,
} from "../types";

/** M026 navigation replaces the M025 four-tab model. */
export type SignalView = "launchpad" | "workbench" | "evidence" | "knowledge" | "settings";

export type Route = {
  view: SignalView;
  investigationId?: string;
};

/** Launchpad: real recents + status via props. Never fictional records. */
export type LaunchpadProps = {
  status: StatusResponse | null;
  recents: InvestigationSummary[];
  recentsLoading: boolean;
  recentsError: string | null;
  notice: string | null;
  openingId: string | null;
  onNew: () => void;
  onImport: () => void;
  onOpen: (id: string) => void;
  onRetryRecents: () => void;
};

/**
 * Workbench: answers WHAT IS WRONG / KNOW / NEXT / WHY / HAPPENED from a
 * live InvestigationResponse. Motion Lab percentages and counters are
 * placeholders and must never ship as measurements: every number here is
 * either a count of local records (labeled as such) or omitted.
 */
export type WorkbenchProps = {
  investigation: InvestigationResponse | null;
  status: StatusResponse | null;
  onNew: () => void;
  onImport: () => void;
  /** Interim: jump to the engine's technician-notes box (GAMMA wires save). */
  onGoNotes: (draft: string) => void;
  onGoEvidence: () => void;
  onGoLaunchpad: () => void;
  onOpenGuide: () => void;
};

/** Standalone evidence forensics: read-only inspection from typed props. */
export type EvidenceViewProps = {
  investigation: InvestigationResponse | null;
  onGoWorkbench: () => void;
  onGoLaunchpad: () => void;
};

export type SettingsViewProps = {
  status: StatusResponse | null;
  investigation: InvestigationResponse | null;
};

export type EvidenceRailProps = {
  view: SignalView;
  investigation: InvestigationResponse | null;
  onGoEvidence: () => void;
  onGoWorkbench: () => void;
};

export type ShellProps = {
  view: SignalView;
  status: StatusResponse | null;
  investigation: InvestigationResponse | null;
  onNavigate: (view: SignalView) => void;
};
