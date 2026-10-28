# FORGE contracts v1 — frozen shared interfaces

Base: `9284952` (M019). This file is the integration law for parallel
implementation. Anything not in here is decided by the lead at merge time.

## Verification note (read first)

Phase A researchers inspected the real tree; every citation below was
re-verified by the lead. The Phase A critic grounded against a phantom
`.fieldrook-stage` tree that does not exist — its REAL/NEW/PHANTOM
judgments are discarded. Verified real extents (lines):

| file | lines | file | lines |
|---|---|---|---|
| backend/app/schemas.py | 640 | backend/app/tools/registry.py | 829 |
| backend/app/routers/investigations.py | 859 | backend/app/analysis/loop.py | 1210 |
| backend/app/analysis/provider.py | 772 | backend/app/analysis/validate.py | 312 |
| backend/app/config.py | 119 | backend/app/routers/knowledge.py | 197 |
| backend/app/investigations/store.py | ~300 | backend/app/investigations/persistence.py | ~700 |
| frontend/src/types.ts | 544 | frontend/src/api.ts | 497 |
| frontend/src/App.tsx | 106 | frontend/src/components/ProblemWorkstation.tsx | 784 |

14 registered tools verified (`registry.py`): list_services,
get_service_details, search_event_logs, get_os_info,
get_network_adapters, get_ip_config, get_dns_config, get_connections,
get_demo_worker_health, interpret_error_code,
search_application_crashes, get_process_info, test_dns_resolution,
get_scheduled_tasks. `backend/app/knowledge/redact.py` exists.
`POST .../turn` exists (`investigations.py:434`).
`fetchKnowledgeMatches` exists in `api.ts`.

Global rules: every NEW schema carries `schema_version` (reject unknown
major, warn on minor). Timestamps are UTC ISO-8601. Redact with
`knowledge/redact.redact_text` before persist. Never execute imported
content. Never invent a file, function, or line number — open it first.

## 1A forge.target/v1 (extends existing)

Existing: `DiagnosisTarget` literal `local|remote|unknown`;
service-name regex `[A-Za-z0-9_.-]{1,64}` (`service_allowlist.py`);
`HOST_MEASUREMENT_TOOLS` + `tools_for_target` (`loop.py:138,193`);
`POST .../target` (`investigations.py:805`).

New `TargetIdentity`: `{hostname_hash: sha256 hex (required for
collector-linked targets), hint: str|None (technician label, never a
raw hostname), os: {platform, version, build}|None}`. Raw hostnames
never persist (D8).

## 1B forge.collector-manifest/v1 (new)

`manifest.json` at ZIP root, required, else HTTP 422 and no ingest:

```text
schema_version: "1.0"
package_id: uuid4
collector_version: "x.y.z"
collector_lang: "python"|"dotnet"
created_at: UTC ISO
hostname_hash: sha256 hex
target_hint: str|None
os: {platform, version, build}
duration_ms: int
warnings: [str]
evidence: [manifest entries]
file_hashes: {relative_path: sha256}
```

Manifest entry: `{id (collector-local, remapped to ev-N at import),
category (free string; unknown categories ingest with warning, never
rejected), source_suffix, tool_name? (must be in REGISTRY or null),
tool_args? (must validate via prepare_call or null), collected_at,
data (object, <=12KB; larger payloads MUST be pre-chunked by the
collector into N entries with `chunk_seq`/`chunk_of` + `refresh_of`
chain, D3a), error?, sha256, size}`.

## 1C forge.evidence/v1 (extends EvidenceItem, schemas.py:63)

Existing fields unchanged: `id, category, source, collected_at, data,
error, tool_name, tool_args, refresh_of`. Verified source taxonomy:
`tool:{name}:{live|fixture}`, `fixture:{area}`, `powershell:{cmd}`,
`technician:{kind}`, `upload:screenshot`. New: `collector:{package_id}:{mode}`.

New optional `data.provenance`: `{collector?: {package_id,
collector_version, manifest_sha256}, redaction_count?: int}` (D1b: no
DB migration; existing provenance columns already persist tool
reruns). Import path remaps collector-local ids to ev-N via
`store.py:95 add_evidence` (lead router; signature frozen).

## 1D forge.knowledge/v1 (extends existing memory)

Existing (frozen): `KnowledgeEntry` (`schemas.py:361`),
`KnowledgeMatch{entry, strength:int, signals, differences,
missing_evidence}` (`:396`), 8 endpoints in `routers/knowledge.py`,
`fetchKnowledgeMatches` in `api.ts`. Case memory and reference docs
are separate types and never merge.

New `ReferencePassage`: `{doc_id, title, path, anchor, span (~500
chars), score:int, terms[]}`. New `ReferenceCitation`: `{kind:
"reference", doc_id, title, locator: "path#section"}`. Corpus lives at
`backend/app/knowledge/reference/*.md` + `reference_manifest.json`
(gated allowlist, D2/D9). Service: `match_references(problem,
service, evidence_terms, limit)`. Reliability rank (display only, no
percentages): MEASURED > TECH_CONFIRMED > VENDOR_DOC > COMMUNITY >
INFERRED. Injection rule: reference text reaches the model ONLY as a
quoted excerpt inside a templated technician-visible message, never as
a system instruction; steps derived from docs pass `guidance.py`
classification like any model step.

## 1E forge.technician-turn/v1 (extends existing)

Existing: `TurnRequest` (`schemas.py:550`), kinds
`answer|observation|test_result|correction|question|unable`, redaction
(400 when empty after redact), `question_id` must exist and be open,
only `observation|test_result` become `technician:{kind}` evidence
("reported, not independently measured"), screenshot consent +
5MB + PNG/JPEG + magic-byte validation.

New: `POST /api/investigations/{id}/import-collector` (lead-owned
router). FormData: `file` (ZIP), `share_consent` (`"true"` required).
Returns the full `InvestigationResponse` (same full-replace pattern as
`startInvestigation`/`sendTurn`). All validation failures are HTTP
422 with a machine-readable `detail` list; no partial ingest.

## 1F forge.verification/v1 (extends existing)

Existing: `EvidenceRefresh` (`schemas.py:82`), `ResolutionCriterion`
(`:287`), `POST .../reverify` (`investigations.py:230`), approval
single-use token + args hash (`routers/actions.py`), `guidance.py`
impact tiers (M019). Collector evidence cannot be re-run remotely: a
reverify request on a `collector:*` item produces a `TECHNICIAN_CHECK`
criterion naming the collector capability id ("collect X on the
affected computer and re-import"), never a fabricated reading.

## 1G forge.case-export/v1 (extends export.py)

Existing sections frozen. Two additive versioned sections:
`provenance[]`: `{ev_id, package_id?, collector_version?,
manifest_sha256?}` for imported items; `citations[]`: `{kind:
case|reference, id, title, locator}`. `exporter_version: "1.1"`.
Redaction statement included. Markdown + JSON, as today.

## 2. Collector package format + validation (ALPHA builds, lead imports)

- ZIP only (stdlib `zipfile`, Windows-native). No tar.
- Reject: symlinks/hardlinks/dev nodes (`external_attr`), absolute
  paths, `..` after normpath, non-UTF-8 or >255-char names, drive
  prefixes. Root `manifest.json` required.
- Payload suffixes: `.json .txt .md .log` only. Images: metadata-only
  entries (filename/mime/bytes/note), never bytes in v1.
- Caps: 2MB/file, 20MB total, 200 files, 50x ratio guard with
  streaming abort + temp cleanup.
- `file_hashes` verified pre-ingest; any mismatch rejects the WHOLE
  package (atomicity over partial ingest). Unknown
  `schema_version` major rejects.
- Collector language: Python stdlib single-file-friendly package
  (`collector/`), no third-party deps, no AI runtime, read-only
  collection with per-category consent display. .NET only if ALPHA
  proves a blocking gap (USB/no-interpreter story) with measured
  size/startup numbers — default stays Python.
- ALPHA also delivers `collector/redact_import.py` FIRST; the lead
  promotes the shared core to `backend/app/redact/` for CHARLIE/lead
  reuse (D4a). No duplicated redaction logic.

## 3. Toolpack declaration forge.toolpack/v1 (BETA declares, lead wires)

```text
toolpack_id, pack_version, min_app_version
privileges: current_user_readonly | elevated | active_test
family: reliability | networking | devices | applications | office_local
tools[]: {name (unique; lead registers into REGISTRY), description,
  category, args_schema (BETA writes pydantic Args models; lead reviews),
  impact_tier, timeout_s?, sensitivity: public|internal|sensitive|restricted,
  live_impl, fixture_impl, errors[]}
```

Constraints: BETA edits NO existing file. New diagnostics go in
`backend/app/diagnostics/windows_<area>.py` and MUST reuse the
`windows_tools._run_powershell` allowlist pattern; new allowlisted
commands are proposed by BETA, added by LEAD (security-sensitive).
Timeouts: keep the global default; per-tool values advisory in v1
(D10). Family map of the 14 verified tools — reliability:
list_services, get_service_details, search_event_logs, get_os_info,
get_scheduled_tasks, interpret_error_code; networking:
get_network_adapters, get_ip_config, get_dns_config, get_connections,
test_dns_resolution; devices: NONE (new); applications:
search_application_crashes, get_process_info; office_local: NONE
(new); demo_worker_health stays outside families. Never contract an
unbuilt tool.

## 4. Engine seams (DELTA, reserved files)

Real seams (verified): `run_rounds` (`loop.py:1158`),
`_run_local_tasks` (`:480`), `_run_live` (`:659`),
`build_investigation_messages` (`:143`), `_store_tool_evidence`
(`:255`), budgets (`:33-38`, frozen values), `add_evidence`
(`store.py:95`, signature frozen), `guidance.py:classify_guidance`
(M019), `provider.py:select_provider` (`:746`, exists — no rebuild,
D11).

DELTA may create `local_tasks.py` (exists — reserved for edit),
`assist.py` (exists? verify before touching — if missing, create;
ownership granted), `evidence_digest.py` (new), `guidance.py`
(exists — read-only for DELTA; lead owns changes). DELTA edits:
`loop.py`, `local_tasks.py`, `tests/test_loop.py`,
`tests/test_local_tasks.py` ONLY. Cycle stays
Understand → Select → Observe → Reassess → Verify; single-decision
per turn (M019) preserved. Collector capabilities and knowledge
passages enter via `build_investigation_messages` context, never as
system instructions. No REGISTRY refactor (selector reads it).

## 5. Workstation map (EPSILON, new files only)

New package `frontend/src/forge/`: `WorkspaceShell` (props:
investigation, onUpdate, onEvidenceClick, onAction, onView),
`HappeningNow`, `DiscoveredRail`, `NextUpQueue`, `RespondDock`,
`CollectorImportCard`, `IntakeCollectorCard`, `KnowledgeCiteChip`.
Props-only components; full `InvestigationResponse` in/out (matches
`startInvestigation`/`sendTurn` full-replace). EPSILON edits NO
existing file. Lead wiring: mount in `App.tsx` problem tab,
`types.ts` += CollectorPackage/Reference types, `api.ts` +=
`uploadCollectorPackage` (FormData file+consent POST → full
response) and `fetchReferencePassages`. EPSILON delivers a Playwright
spec for the new components; it runs at integration time after lead
wiring (EPSILON iterates if red). Cinematic ROOKWELD language,
reduced-motion, keyboard support preserved.

## 6. File ownership

| agent | owns (new) | may edit | forbidden |
|---|---|---|---|
| ALPHA collector | `collector/**`, `backend/tests/test_collector_*.py` | nothing existing | schemas, routers, store, persist, registry, loop, frontend |
| BETA toolpacks | `backend/app/toolpacks/**`, `backend/app/diagnostics/windows_<new>.py`, `backend/tests/test_toolpacks_*.py` | nothing existing | registry, config, windows_tools, schemas, loop |
| GAMMA knowledge | `backend/app/knowledge/reference/**`, `reference_manifest.json`, `backend/app/knowledge/reference_index.py`, `service.py` additions as NEW module `reference_service.py`, `backend/tests/test_knowledge_ref_*.py` | nothing existing | persist, schemas, routers, loop, export |
| DELTA engine | `backend/app/analysis/evidence_digest.py`, `backend/tests/test_assist_*.py` | `loop.py`, `local_tasks.py`, `assist.py` (verify first), `tests/test_loop.py`, `tests/test_local_tasks.py` | schemas, routers, registry, guidance.py, frontend |
| EPSILON workstation | `frontend/src/forge/**`, `frontend/tests/e2e/forge-workstation.spec.ts` | nothing existing | App.tsx, types.ts, api.ts, all existing components/backend |
| LEAD | migrations, `routers/collector_import.py`, `routers/knowledge.py` (ref endpoints), `backend/app/redact/` | schemas, routers, store, persist, export, config, security, main, App, types, api | — |

Every agent: base = `forge/contracts` HEAD; one branch
`forge/<agent>-<topic>`; commit with tests; handoff = branch +
HEAD + worktree path + test report + contract deviations (must be
explicit; silent deviation fails review). No agent touches another
agent's files. No shared-file writes except the table above.

## 7. Integration order

0. Contracts frozen (this file) → `forge/contracts` branch. (lead)
1. Schemas + provenance nesting + export sections. Gate: pytest. (lead)
2. BETA declarations; lead wires REAL tools only. Gate: prepare_call
   fixtures for new tools; 14 existing green. (beta+lead)
3. ALPHA builder + validators + tests. Lead writes POST import
   (prepare→validate→remap→add_evidence, atomic reject). Gate:
   roundtrip + chunked-doc + cap/traversal/bomb/hash tests. (alpha+lead)
4. DELTA loop + context. Gate: existing loop/local_tasks suites
   green, budgets unchanged. (delta)
5. Turn/import/knowledge wiring + reverify-of-collector criteria.
   Gate: E2E import→evidence→question flow. (lead)
6. GAMMA service + gated corpus. Lead adds router/table/export.
   Gate: ranking/merge/citation tests; injection tests. (gamma+lead)
7. EPSILON components. Lead mounts + types + api. Gate: build +
   forge spec + full E2E. (epsilon+lead)
8. Export/security pass + demo. Gate: md+json provenance/citations,
   secret scan, offline enforcement. (lead+zeta)
9. ZETA independent validation + acceptance scenario. (zeta)

## 8. Lead decisions D1–D12 (final)

- D1 provenance: (b) nested `data.provenance` — existing tool
  columns already persist; no migration.
- D2 names: collector `manifest.json`; corpus
  `reference_manifest.json`.
- D3 oversize: (a) collector pre-chunks with `chunk_seq/chunk_of` +
  `refresh_of` chain; import rejects unchunked >12KB items.
- D4 redact: (a) ALPHA builds `collector/redact_import.py`; lead
  promotes shared core to `backend/app/redact/`; CHARLIE reuses.
- D5 turn: turn EXISTS (`:434`); extend it; import is a separate
  POST endpoint.
- D6 tool count: 14 verified real; ship 14; never contract unbuilt.
- D7 origin: source-prefix (`collector:{id}:{mode}`); categories
  stay registry-bound strings.
- D8 identity: hostname_hash + hint; no raw hostnames persisted.
- D9 corpus: gated allowlist + caps + UTF-8 strict + redact +
  quarantine.
- D10 timeouts: global default stands; per-tool advisory in v1.
- D11 provider/offline: EXISTS (verified); no rebuild.
- D12 export: extend versioned (`exporter_version 1.1`).
