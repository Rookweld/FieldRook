# FieldRook — Evidence Trials

**Operation Prove It:** public, audit-friendly walkthrough of three deterministic synthetic Windows troubleshooting scenarios using FieldRook's actual FastAPI/evaluation code path.

The site in `docs/evidence-trials` is static and read-only, with no remote diagnostics, tracking scripts, external JavaScript/CSS, client credentials, or model API keys.

## The three trials

1. **The Five-Minute Phantom** (`task-phantom`): a task matches a reported five-minute PowerShell-window cadence. It is a suspect, not a proven cause. No corrective action is proposed.
2. **The Measured Recovery** (`resolve-manual-worker`): a failing demo-worker fixture is followed by a synthetic manual-intervention claim, then a fresh reading that supports `VERIFIED_RESOLVED`.
3. **The Fix That Wasn't** (`resolve-still-failing`): an identical intervention claim followed by a fresh failing reading results in `NOT_RESOLVED`.

No case executes a corrective action. The worker cases test manual claims and follow-up measurements; they are not autonomous repair demos.

## Reproduce

Install requirements from `backend/requirements.txt` in a supported Python environment. From repository root:

```powershell
cd backend
python -m eval.run --results-dir ../.evidence-eval-run
cd ..
$result = Get-ChildItem .evidence-eval-run\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python scripts/evidence_trials/export.py --gauntlet $result.FullName
python scripts/evidence_trials/check.py
python -m http.server 4179 --directory docs/evidence-trials
```

Open `http://127.0.0.1:4179/`. Loading through `file://` does not permit JSON fetch in many browsers.

## Provenance and limitations

- `backend/eval/cases.py`: canonical synthetic scenarios and expected checks.
- `backend/eval/run.py`: actual offline gauntlet, citation and authorization checks, independent remeasurement.
- `scripts/evidence_trials/export.py`: drives three cases via FastAPI TestClient and exports allowlisted, provenance-linked fixture evidence.
- `scripts/evidence_trials/check.py`: validates claims, source IDs, statuses and absence of real executions.
- `data/trials.json`: generated public snapshot from the fixture suite; volatile IDs and private/host fields are excluded.

The site does not measure live AI inference or real-world troubleshooting success. The demo's model reasoning is simulated and labeled. The source commit and run timestamp are shown for reproducibility.

## Publication

`.github/workflows/evidence-trials-pages.yml` regenerates the three trials from fixture-only tests, checks the export, and deploys `docs/evidence-trials` through GitHub Pages when Pages is configured to use GitHub Actions. Do not commit real workstation logs to this directory.

Apache-2.0, as part of FieldRook.