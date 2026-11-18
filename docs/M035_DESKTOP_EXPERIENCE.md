# M035 — Desktop Experience & Owned-Service Recovery

Branch: `m035/desktop-experience`
Base: M034 commit `c3aeb9f`
Scope: Native Windows shell only. No diagnostic-model, evidence, authorization or backend schema changes.

## What changed

### Visible startup instead of a silent wait
- FieldRook now displays a small native startup window before launching the packaged local server.
- It explains the current stage: port discovery, service launch, evidence-store preparation, and workspace opening.
- The operator can cancel. Cancellation is checked after asynchronous port and instance probes and cancels the health wait.
- The splash closes after the main WebView2 window is visible.
- `--smoke` and `--help` keep their headless/console behavior.

### Real recovery after a backend crash
- On unexpected server exit the app shows a non-blocking error overlay, with **Restart service**, **Open logs** and **Exit FieldRook**.
- Retry performs a brief live-health check. If the child is still healthy, it simply reloads the UI.
- Otherwise it shuts down only the owned child through the existing process fence and job object, starts a fresh server on the SAME port, checks service/runtime identity, and reloads WebView2.
- If another process has taken the dead service's port, recovery refuses to attach to it and explains the port conflict.
- Recovery does not delete the database, evidence or settings. It does not kill or attach to unrelated processes.
- Exit events from retired children no longer produce false crash notifications after an intentional shutdown/restart.
- The old job object is retired on restart, so a repeated attempt doesn't leak old job handles.

### Actionable, quieter error handling
- The backend-crash UI no longer dumps raw server logs into a modal dialog.
- Logs stay in the normal per-user location: `%LOCALAPPDATA%\\FieldRook\\logs`.
- **Open logs** launches the folder in Explorer for a technician, with a visible fallback path.
- Startup failures include the log-folder path, not a large raw log tail.
- Repeated retry clicks are ignored while recovery is active.

## Boundaries and deferred checks
- **Verified locally:** native .NET Release solution build and Git diff checks.
- **Not yet proven:** packaged restart from a real crash, WebView2 runtime-missing UX, cancellation timing, upgrade and installer behavior on a clean Windows PC.
- Full regression/E2E and external-user acceptance deliberately deferred at the user's request.
- Published rc.2 artifacts and mainline/public releases are unchanged. This change is not an installer or release.

## Follow-on product work
- Complete and streamline the case close/reopen/report handoff flow.
- Make diagnostics accessible from Settings (with safe, explicitly consented sharing).
- Verify a packaged installation, runtime requirements, update/repair and support-bundle strategy.
- Complete a final real-machine acceptance gate before distributing externally.
