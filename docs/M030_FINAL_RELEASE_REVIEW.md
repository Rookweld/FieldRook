# M030 Final Release Review - FieldRook EvidenceTrials

**Review date:** 2026-11-17
**Working tree:** `C:\dev\FieldRook_EvidenceTrials`
**Branch:** `m030/probe-correctness`
**Base commit:** `acc6e07`
**Version file:** `0.6.0-rc.1` (already-published pre-release version; no new package published)

## Decision

**GO for a source-code pull request / merge after the owner approves and commits the reviewed changes.**
**NOT YET GO for a newly distributed Windows binary.** This review did not create,
publish, or smoke-test a newly frozen release package. The existing v0.6.0-rc.1
artifact must not be represented as containing these uncommitted M030 fixes.

## Scope and findings

- **D1 - probe recovery:** explicit connection tests bypass cached negative
  Ollama detection and refresh model capabilities; background caching remains.
  Recovery and stale-capability scenarios have regression coverage.
- **D2 - cancellation:** a pre-set flag avoids cold capability probes; a
  mid-flight flag interrupts waiting for slow `/api/tags` or `/api/show`
  without inventing an assessment or discarding evidence.
- **D3 - API-style honesty:** before any probe, the local provider reports
  `unresolved`, without network I/O from `GET /api/providers`.
- **D5 - loopback security:** direct sync/async probe and capability-fetch
  functions reject external URLs before creating HTTP clients. Local Ollama
  and OpenAI-compatible calls do not forward cloud bearer credentials.
- **Deferred (not tested as resolved):** D4 duplicate concurrent probes;
  D6 vision/capability status flapping after cache expiry.

## Verified on Fury

| Gate | Exact result |
| --- | --- |
| Backend full suite, **isolated Python 3.12** | **734 passed, 4 skipped, 2 warnings**, exit 0, 334.37 s |
| Focused local-probe / cancellation / task suites | **63 passed, 1 warning**, exit 0 |
| Frontend `pnpm install --frozen-lockfile` | PASS, existing lockfile unchanged |
| Frontend `pnpm run build` | PASS, TypeScript + production Vite build |
| Browser E2E `pnpm run test:e2e` | **98 passed**, exit 0, ~4.4 min |
| Native `dotnet test FieldRook.slnx -c Release` | **66 passed**, 0 failed, exit 0 |
| WPF `dotnet build` Release | PASS, 0 warnings, 0 errors |
| `python -m pip check` in checkout venv | PASS, no broken requirements |
| `git diff --check` | PASS |
| Real Ollama probe on 127.0.0.1:11434 | PASS; model `qwen3:8b` advertised completion/tools/thinking |
| Real native Ollama chat from isolated backend | PASS; received `OK` (16.64 s including cold load) |

Backend test environment is `backend\.venv` with Python 3.12.10,
FastAPI 0.163.1, Pydantic 2.14.3, HTTPX 0.28.1, pytest 9.2.0, and Uvicorn 0.54.0.
The venv is ignored by Git and the E2E runner automatically used its interpreter.
Warnings: existing Starlette/httpx TestClient deprecation, and intentional
duplicate-name warning in the archive rejection test.

## Security/dependency audit

- `pnpm audit --prod --audit-level moderate`: **no known vulnerabilities**.
- Full `pnpm audit`: **one HIGH advisory** for dev-tool dependency
  `picomatch@4.0.7`, via Vite/fdir/tinyglobby:
  [GHSA-fc5q-39xc-vjpf / CVE-2026-112366](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
  As checked on 2026-11-17, no patched version was listed. This is not
  a React production runtime dependency. Restrict development/build tooling
  to trusted local or CI inputs and monitor upstream; do not claim the full
  dependency tree is free of vulnerabilities.
- No secrets or API keys were added to source files during M030 review.

## Remaining release work (before publishing a new binary)

1. **Packaging interpreter mismatch:** `packaging/desktop/build.ps1` selects
   the ambient `python.exe` (currently Python **3.14.3** on Fury), while the
   validated and CI-targeted backend uses **3.12.10**. Choose/pin the
   packaging interpreter and verify the frozen output with that toolchain.
2. Python `backend/requirements.txt` has lower bounds, not a frozen runtime
   lock; record/pin tested production build dependencies for reproducibility.
   Local frontend testing used Node 24/pnpm 12 while CI uses Node 20/pnpm 9.
3. Existing GitHub Actions validation runs backend unit tests and frontend
   build, but not Playwright E2E or native .NET tests. Add release gates.
4. For a **new** Windows distribution: choose the new version, rebuild the
   one-dir package and shell in a separate output directory, verify
   `--version`, app lifecycle, bundled worker, BOM, SHA-256 hashes,
   and a clean-machine smoke check. Do not overwrite the published rc.1.
5. Track deferred D4/D6 behavior independently. The real Ollama smoke test
   validates transport, not deep diagnostic reasoning quality.

## Reproduction commands

```powershell
cd C:\dev\FieldRook_EvidenceTrials\backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

cd ..\frontend
pnpm install --frozen-lockfile
pnpm run build
pnpm run test:e2e

cd ..\native-shell
dotnet test .\FieldRook.slnx -c Release --nologo --verbosity quiet
dotnet build .\src\FieldRook\FieldRook.csproj -c Release --nologo --verbosity quiet

git -C C:\dev\FieldRook_EvidenceTrials diff --check
git -C C:\dev\FieldRook_EvidenceTrials status --short --branch
```

**Change control:** No commit, merge, push, tag, or release publication was
performed in this review. Review the untracked
`backend/tests/test_local_probe_async.py` along with the five modified tracked
files before staging.
