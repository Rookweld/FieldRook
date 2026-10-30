# SIGNALFORGE Wiring Guide (GAMMA → BETA integration)

Owner: M026 GAMMA (branch `m026/gamma-wiring`). Base: `m026/desktop-rebirth @ 35973fb`.
Audience: lead at integration, BETA for view-side expectations.

Rule of the merge: GAMMA files land whole; BETA view files receive ONLY the
insertions in section 5 (hook calls + prop passing, zero markup/CSS changes).
BETA views are NOT in this worktree — every patch below is anchored on the
exported component symbol so it applies without line numbers.

## 1. What GAMMA delivers (file inventory)

| File | Kind | Notes |
|---|---|---|
| `frontend/src/api.ts` | EXTENDED (append-only, +52/−0) | section 2; no signature touched |
| `frontend/src/signalforge/shellBridge.ts` | NEW | section 4; no React dependency |
| `frontend/src/signalforge/hooks/formatError.ts` | NEW | shared honest-error formatter |
| `frontend/src/signalforge/hooks/useViewState.ts` | NEW | `{view, investigationId}` + persistence |
| `frontend/src/signalforge/hooks/useLaunchpad.ts` | NEW | status + real recents |
| `frontend/src/signalforge/hooks/useInvestigation.ts` | NEW | open-case container |
| `frontend/src/signalforge/hooks/useGuidedChecks.ts` | NEW | plan steps, hypotheses, target |
| `frontend/src/signalforge/hooks/useProviders.ts` | NEW | provider list/test/switch |
| `frontend/src/signalforge/hooks/useServices.ts` | NEW | M025 service lookup, preserved |
| `frontend/src/signalforge/hooks/useTools.ts` | NEW | tool catalogue |
| `frontend/src/signalforge/hooks/useActions.ts` | NEW | propose/approve/reject/execute |
| `frontend/src/signalforge/hooks/useResolution.ts` | NEW | resolution plans lifecycle |
| `frontend/src/signalforge/hooks/useCollectorImport.ts` | NEW | zip import + validation |
| `frontend/src/signalforge/hooks/useKnowledge.ts` | NEW | library + per-case knowledge |
| `frontend/src/signalforge/hooks/useExport.ts` | NEW | shell save / browser download |
| `frontend/src/signalforge/hooks/index.ts` | NEW | barrel (views import from here) |
| `frontend/src/signalforge/hooks/wiring.contracts.ts` | NEW | tsc-enforced contract check |
| `frontend/tests/e2e/signalforge-wiring.spec.ts` | NEW | backend-surface pins |
| `WIRING-GUIDE.md` (this file) | NEW | integration patches |

Backend: ZERO changes. No blocker report (every hook maps to an existing
endpoint; see section 6).

## 2. `api.ts` extensions (new exports only)

```ts
export type ExportFormat = "markdown" | "json";
export type DesktopStatusResponse = StatusResponse & { runtime: string };
export function getDesktopStatus(): Promise<DesktopStatusResponse>;
export function investigationExportUrl(id: string, format: ExportFormat): string;
export function fetchInvestigationExport(id: string, format: ExportFormat): Promise<string>;
export function fetchKnowledgeExport(entryId: string, format: ExportFormat): Promise<string>;
```

- `runtime` is the M025 Z1 identity field (`"desktop"` frozen vs `"dev"`
  checkout). The backend already returns it; the old `StatusResponse`
  shape never carried it, so `getDesktopStatus` is the typed reader.
  `getStatus()` is untouched.
- `investigationExportUrl` mirrors the existing `knowledgeExportUrl`
  (views previously hardcoded this path inline).
- The `fetch*` helpers return response TEXT (exports are markdown/JSON
  documents, not the JSON envelope `request<T>` parses).

## 3. Hook catalog (import from `../hooks` relative to views)

All bindings follow one shape: `{ investigation, onUpdate, onError?, disabled? }`.
Every mutation obeys the M025 full-replace pattern (server returns the whole
`InvestigationResponse`; the hook calls `onUpdate`). `busy` is a string op
key or boolean; `error` is one honest sentence. Only one mutation runs at a
time per hook; calls made while busy (or with nothing open) set `error` and
return null — they never throw into the view.

- `useViewState()` → `{ state: {view, investigationId}, go(view),
  openInvestigation(id), startNew(), reset() }`. Persisted under
  `signalforge.view.v1`. `reset()` is the error-boundary recovery target.
- `useLaunchpad(limit = 10)` → `{ status, recents, loading, error, refresh }`.
  `status` is `DesktopStatusResponse | null`; `recents` are REAL persisted
  cases (same store as History).
- `useInvestigation({initial?, onError?})` → `{ investigation, busy, error,
  start(args), open(id), refresh(), send(turnArgs), followUp(message),
  addNote(text), cancel(), reverify(evidenceId), update(next), clearError() }`.
  The open-case owner; `update` lets sibling hooks share one state object.
- `useGuidedChecks(binding)` → `{ busy, error, completeStep(stepId, outcome),
  markImpossible(stepId, reason), setHypothesis(id, status, reason),
  setTargetValue(target), clearError() }`.
- `useProviders(binding)` → `{ providers, loading, testing, busy, error,
  localResult, refresh(), testLocal(), switchTo(provider, confirmCloud),
  clearError() }`. Cloud switches require `confirmCloud: true`.
- `useServices()` → `{ services, mode, selected, diagnostics, assessment,
  loading, busy, error, select(name), loadDiagnostics(useFixtures?),
  analyze(useFixtures?), clearError() }`. M025 service lookup intact.
- `useTools()` → `{ tools, loading, error, refresh() }`.
- `useActions(binding)` → `{ busy, error, approvedIds, propose(actionId,
  target, reason), approve(proposalId), reject(proposalId),
  execute(proposalId), clearError() }`. Approval tokens stay in memory
  only; `approvedIds` exposes presence, never the token. `execute`
  without `approve` fails with an honest message; a failed execute drops
  the ticket and resyncs from the server.
- `useResolution(binding)` → `{ busy, error, template,
  loadTemplate(actionId), create(input), baseline(planId),
  recordManual(planId, description), linkExecution(planId, executionId),
  verify(planId), clearError() }`. `create` takes everything except
  `investigationId` (the binding supplies it).
- `useCollectorImport({investigationId, onUpdate, onError?, disabled?})` →
  `{ busy, error, importFile(file, consent), importShellFile(result,
  consent), clearError() }`. Reuses `forge/collectorPackage` validators.
  Consent is mandatory (backend rejects without it).
- `useKnowledgeLibrary()` → `{ entries, loading, error, query,
  setQuery(patch), refresh(), remove(entryId) }`.
- `useInvestigationKnowledge(binding)` → `{ matches, passages, citations,
  referenceMessage, busy, error, savedMessage, loadMatches(limit?),
  loadReferences(limit?), recordCause(text), recheck(entryId),
  clearError() }`. Matches/references load explicitly, never on mount.
- `useExport()` → `{ busy, error, investigationUrl(id, format),
  knowledgeUrl(entryId, format), downloadInvestigation(id, format),
  downloadKnowledge(entryId, format), clearError() }`.
  `download*` uses the native save dialog under the shell, else a browser
  download (section 4 fallback matrix).

Shared error text comes from `formatApiError(e, what)`:
`"<what> failed (HTTP <status>): <detail>"`, matching M025 wording.

## 4. Shell bridge (`signalforge/shellBridge.ts`)

Typed allowlisted client for contract section 2 (`{op, id, params}` →
`{id, ok, result | error}`). Only `openFile`, `saveFile`, `getVersion`
are ever sent; anything else cannot be constructed.

```ts
isShellBridgeAvailable(): boolean;
shellGetVersion(): Promise<{ version: string }>;
shellOpenFile(args?: { accept?: string; title?: string }): Promise<{
  path: string; name: string; sizeBytes: number; contentBase64: string | null;
}>;
shellSaveFile(args: { filename: string; text: string; mime?: string }): Promise<{
  path: string; bytesWritten: number;
}>;
onShellEvent(listener: (event: ShellPushEvent) => void): () => void; // unsubscribe
class ShellBridgeError extends Error { code: "unavailable" | "timeout" | "rejected" | "protocol"; }
```

Fallback matrix (implemented in `useExport` / `useCollectorImport`):

| Situation | Behaviour |
|---|---|
| `window.chrome.webview` absent | browser file picker / anchor download |
| shell dialog cancelled or errors (`rejected`) | honest message; NO second download prompt |
| shell timeout / malformed reply | honest message; no silent retry |
| `openFile` returns path-only (`contentBase64: null`) | importer says the browser cannot read the path and asks for the picker |

PROVISIONAL assumptions for ALPHA to confirm at integration (all
documented in code; none block the browser path):

1. `openFile` result SHOULD include `contentBase64` (bytes), because a
   page cannot read an arbitrary native path. Path-only results degrade
   honestly (see matrix).
2. Push events arrive as id-less `{event, payload}` messages. The only
   known event is `collector-dropped: {path, name}` for window zip drops.
   Real file drops ALSO arrive via the browser `DataTransfer` as `File`
   objects — views should prefer those and pass them to `importFile`.
3. Dialog timeouts are 120 s, `getVersion` 10 s.

## 5. Per-file insertion patches (lead applies at integration)

Each patch: target file, anchor symbol, exact insertion. No other view
change is permitted.

### 5.1 `frontend/src/App.tsx` — anchor: `export function App()`

BETA owns the nav restructure; this patch supplies the state it runs on.
Replace the tab state line:

```tsx
// REMOVE: const [tab, setTab] = useState<"problem" | "service" | "history" | "knowledge">("problem");
// ADD (with other imports):
import { useViewState } from "./signalforge/hooks";
// ADD (replacing the useState line):
const { state: nav, go, openInvestigation, startNew, reset } = useViewState();
```

Then: `nav.view` drives which SIGNALFORGE view renders;
`nav.investigationId` seeds the workbench (`openInvestigation` from
launchpad recents / evidence / knowledge hits); `ErrorBoundary onReset`
calls `reset()`; `FirstRunGate` stays mounted above the boundary.
M025 `seeded`/`setTab("problem")` behaviour maps to
`openInvestigation(id)` / `go("launchpad")`.

### 5.2 `frontend/src/signalforge/views/Launchpad.tsx` — anchor: `export function Launchpad(`

```tsx
import { useLaunchpad } from "../hooks";
// Props IN (BETA keeps its own markup; these two callbacks are the only wiring surface):
//   { onOpenInvestigation: (id: string) => void; onStartNew: () => void; }
// Top of component body:
const { status, recents, loading, error, refresh } = useLaunchpad(10);
```

Render mapping: `status` → identity strip (`service`, `runtime`,
`version`, `model_mode`); `recents` → case list (each row opens via
`onOpenInvestigation(row.investigation_id)`); `loading`/`error` →
existing pending/error slots. NEVER render placeholder cases.

### 5.3 `frontend/src/signalforge/views/Workbench.tsx` — anchor: `export function Workbench(`

The workbench owns the open case; every other hook binds to it.

```tsx
import {
  useActions, useCollectorImport, useExport, useGuidedChecks,
  useInvestigation, useInvestigationKnowledge, useProviders, useResolution,
} from "../hooks";
// Props IN: { investigationId: string | null; onError?: (message: string) => void; }
// Top of component body:
const inv = useInvestigation({ onError });
useEffect(() => {
  if (investigationId && investigationId !== inv.investigation?.investigation_id) void inv.open(investigationId);
}, [investigationId]); // eslint-free repo: keep deps minimal and honest
const binding = { investigation: inv.investigation, onUpdate: inv.update, onError, disabled: inv.busy !== null };
const guided = useGuidedChecks(binding);
const providers = useProviders(binding);
const actions = useActions(binding);
const resolution = useResolution(binding);
const knowledge = useInvestigationKnowledge(binding);
const importer = useCollectorImport({ investigationId: inv.investigation?.investigation_id ?? null, onUpdate: inv.update, onError });
const exporter = useExport();
```

WHAT/WHY/NEXT/HAPPENED answers read from `inv.investigation`
(`assessment`, `hypotheses`, `plan`, `questions`, `activity`) as typed
props. Unknowable values keep truthful labels or are omitted (contract
section 3). Start form → `inv.start({problem, serviceName?, useFixtures?,
shareConsent, screenshot?, target?, provider?})`; turns → `inv.send`;
notes → `inv.addNote`; cancel → `inv.cancel`; re-verify → `inv.reverify`.
Provider UI → `providers.*`; guided steps → `guided.*`; action cards →
`actions.*` (approve and execute stay separate buttons); plan UI →
`resolution.*`; knowledge strip → `knowledge.loadMatches/loadReferences/
recordCause/recheck`; import card → `importer.importFile` (picker/drop
`File`) or `importer.importShellFile` (native dialog result); export
buttons → `exporter.downloadInvestigation`.

### 5.4 `frontend/src/signalforge/views/Evidence.tsx` — anchor: `export function Evidence(`

```tsx
import { useCollectorImport, useInvestigation } from "../hooks";
// Props IN: { investigationId: string | null; onError?: (message: string) => void; }
// Top of component body:
const inv = useInvestigation({ onError });
useEffect(() => {
  if (investigationId && investigationId !== inv.investigation?.investigation_id) void inv.open(investigationId);
}, [investigationId]);
const importer = useCollectorImport({ investigationId, onUpdate: inv.update, onError });
```

Render `inv.investigation?.evidence` with provenance as today; re-verify
buttons → `inv.reverify(evidenceId)`; import card →
`importer.importFile` / `importer.importShellFile` (same consent rule as
5.3). 422/409 details surface verbatim — no partial ingest exists.

### 5.5 `frontend/src/signalforge/views/Knowledge.tsx` — anchor: `export function Knowledge(`

```tsx
import { useExport, useKnowledgeLibrary } from "../hooks";
// Props IN: none required (library is global).
// Top of component body:
const library = useKnowledgeLibrary();
const exporter = useExport();
```

Filters → `library.setQuery({q?, category?, outcome?})`; delete →
`library.remove(entryId)`; export links → `exporter.knowledgeUrl(entryId,
format)` for hrefs or `exporter.downloadKnowledge(entryId, format)` for
buttons. Per-case matches/references live in the workbench (5.3), not here.

### 5.6 `frontend/src/signalforge/views/Settings.tsx` — anchor: `export function Settings(`

```tsx
import { shellGetVersion, useProviders, useServices, useTools } from "../hooks";
// Props IN: { investigation: InvestigationResponse | null; onUpdate: (next: InvestigationResponse) => void; onError?: (message: string) => void; }
// Top of component body:
const providers = useProviders({ investigation, onUpdate, onError });
const services = useServices();
const tools = useTools();
const [shellVersion, setShellVersion] = useState<string | null>(null);
useEffect(() => {
  let cancelled = false;
  shellGetVersion().then(
    (v) => { if (!cancelled) setShellVersion(v.version); },
    () => { if (!cancelled) setShellVersion(null); }, // plain browser: no shell version
  );
  return () => { cancelled = true; };
}, []);
```

Provider section → `providers.*` (list/test/switch); service lookup →
`services.*` (M025 capability preserved); tool catalogue → `tools.tools`;
identity row → `shellVersion` (null = browser preview, label honestly).
Motion preference stays DELTA-owned (`fieldrook.motion.v1`) — this file
must not invent a second motion key.

## 5.5 Lead integration resolutions (2026-10-30)

- `openFile` bytes CONFIRMED: the shell returns
  `{path, name, sizeBytes, contentBase64}` (16 MiB cap, oversize fails
  honestly). `shellOpenFile` parses it as coded — no client change.
- `saveFile` direction REVERSED from the provisional sketch: the shell
  keeps `{fileName, contentBase64}` (ALPHA's tested parser untouched)
  and now returns `{path, bytesWritten}`; the client encodes
  UTF-8 → base64 in `shellBridge.ts` (`useExport` untouched).
- `getVersion` CONFIRMED plus: the shell adds a top-level `version`
  (== shell assembly version) alongside `{shell, server, runtime}`.
- Push events: the shell posts `{kind:"fieldrook:file", fileName,
  path}`; the client normalizes it to `collector-dropped`. The
  provisional `{event:"collector-dropped"}` wire shape was NOT adopted.
- Shell error records `{code, message}` are surfaced verbatim in
  `ShellBridgeError.message` (code stays `rejected` for user cancels).
- Views shipped prop-driven from App/engine state, so most §5 hook
  insertions had no surface and were deliberately NOT applied (see the
  integration commit): `useViewState` (App nav + persistence),
  `useCollectorImport` (window drop-to-import), `shellGetVersion`
  (Settings identity row) are live; the rest ship as tested API for
  future surfaces.

## 6. M025 capability preservation checklist

| Capability | Hook(s) | Backend endpoint(s) — all existing |
|---|---|---|
| investigations (start/open/list) | useInvestigation, useLaunchpad | POST/GET `/api/investigations`, GET `.../{id}` |
| guided checks (steps/hypotheses) | useGuidedChecks | plan step + hypothesis + target routes |
| targets | useGuidedChecks.setTargetValue, start `target` | POST `.../target`, start form |
| import + validation | useCollectorImport | POST `.../import-collector` |
| provenance | rendered from `InvestigationResponse` (no hook needed) | — (read model) |
| citations/references | useInvestigationKnowledge | GET `.../knowledge/references` |
| providers | useProviders | GET `/api/providers`, POST `.../provider`, POST `/api/providers/local/test` |
| offline/simulated | start `useFixtures`, services `useFixtures` | existing flags |
| approvals | useActions approve/reject | POST `/api/proposals/.../approve\|reject` |
| cancellation | useInvestigation.cancel | POST `.../cancel` |
| verification | useResolution, useActions | plan verify + execution outcome |
| export | useExport | GET `.../export`, GET `/api/knowledge/.../export` |
| history/persistence | useLaunchpad, useViewState | GET `/api/investigations`, localStorage view key |
| service lookup | useServices | `/api/services*`, `/api/incidents/analyze` |
| knowledge library | useKnowledgeLibrary | `/api/knowledge*` |
| knowledge matches/recheck | useInvestigationKnowledge | matches + recheck routes |
| tools catalogue | useTools | GET `/api/tools` |
| status/identity | useLaunchpad | GET `/api/status` (+ `runtime`) |

## 7. Verification (run in THIS worktree)

```powershell
cd C:\tmp\m26-wt-gamma\frontend
pnpm install            # once; pnpm 12.9.1
pnpm build              # gate: tsc --noEmit + vite build (runs wiring.contracts.ts)
pnpm exec playwright test tests/e2e/signalforge-wiring.spec.ts  # backend-surface pins
```

- `tsc --noEmit` type-checks `wiring.contracts.ts`: every hook, binding,
  api.ts extension, and bridge signature. A drifted contract fails here.
- The wiring spec spins the real backend (:8123) + Vite (:4173) via the
  repo `playwright.config.ts` webServer entries; no BETA view needed.
- Secret scan on new files: no credentials, tokens, or keys are added
  (approval tokens live in memory only and are never logged).
- Backend: untouched — no pytest required. If a backend gap appears at
  integration, it needs a lead-approved blocker report first (contract
  section 5); GAMMA files none.
