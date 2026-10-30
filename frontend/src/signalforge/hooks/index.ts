/**
 * SIGNALFORGE wiring barrel (GAMMA). BETA views import hooks from here;
 * see WIRING-GUIDE.md at the worktree root for the per-view patches.
 */
export { formatApiError } from "./formatError";
export { useActions, type ActionsBinding } from "./useActions";
export { useCollectorImport, type CollectorImportBinding } from "./useCollectorImport";
export { useExport } from "./useExport";
export {
  useGuidedChecks,
  type GuidedChecksBinding,
} from "./useGuidedChecks";
export {
  useInvestigation,
  type UseInvestigationOptions,
} from "./useInvestigation";
export {
  useInvestigationKnowledge,
  useKnowledgeLibrary,
  type InvestigationKnowledgeBinding,
  type KnowledgeQuery,
} from "./useKnowledge";
export { useLaunchpad } from "./useLaunchpad";
export { useProviders, type ProvidersBinding } from "./useProviders";
export {
  useResolution,
  type ResolutionBinding,
  type ResolutionCreateInput,
} from "./useResolution";
export { useServices } from "./useServices";
export { useTools } from "./useTools";
export {
  useViewState,
  type SignalforgeView,
  type SignalforgeViewState,
} from "./useViewState";
export {
  isShellBridgeAvailable,
  onShellEvent,
  shellGetVersion,
  shellOpenFile,
  shellSaveFile,
  ShellBridgeError,
  type ShellBridgeErrorCode,
  type ShellOpenFileArgs,
  type ShellOpenFileResult,
  type ShellOp,
  type ShellPushEvent,
  type ShellSaveFileArgs,
  type ShellSaveFileResult,
  type ShellVersionResult,
} from "../shellBridge";
