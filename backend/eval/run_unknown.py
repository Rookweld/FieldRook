"""Unknown-problem evaluation runner (M016).

Offline, hermetic, deterministic: a temp database, fixture tools, no model
key. Run: `python eval/run_unknown.py [--results-dir DIR]`.
Exit code is non-zero if any evaluated case fails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["FIELDROOK_OFFLINE"] = "1"
os.environ["FIELDROOK_FIXTURES"] = "always"
os.environ["MODEL_API_KEY"] = ""
os.environ["FIELDROOK_DB_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="fieldrook-unknown-")) / "unknown.db"
)
os.environ["FIELDROOK_DEMO_STATE"] = tempfile.mkdtemp(prefix="fieldrook-unknown-demo-")
os.environ.pop("FIELDROOK_FIXTURE_WORKER", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from eval.unknown_problems import CASES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="FieldRook unknown-problem evaluation")
    parser.add_argument("--results-dir", default=str(Path(__file__).resolve().parent / "results"))
    args = parser.parse_args()
    client = TestClient(app)
    results: list[dict] = []
    for case_id, category, reference, fn in CASES:
        started = time.monotonic()
        try:
            passed, failures, detail = fn(client)
        except Exception as exc:  # noqa: BLE001 - one case must not kill the run
            passed, failures = False, [f"{type(exc).__name__}: {exc}"]
            detail = traceback.format_exc(limit=3)
        results.append(
            {
                "id": case_id,
                "category": category,
                "passed": passed,
                "latency_s": round(time.monotonic() - started, 1),
                "detail": detail,
                "failures": failures,
                "reference": reference,
            }
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"unknown-{stamp}.json"
    out_path.write_text(
        json.dumps(
            {"created_at": stamp, "suite": "unknown-problems", "results": results}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"\n{'CASE':28} {'RESULT':8} {'LAT(s)':7} DETAIL")
    for item in results:
        verdict = "PASS" if item["passed"] else "FAIL"
        print(f"{item['id']:28} {verdict:8} {item['latency_s']:7} {item['detail']}")
        for failure in item["failures"]:
            print(f"  - {failure}")
    passed = sum(1 for item in results if item["passed"])
    print(f"\n{passed}/{len(results)} unknown-problem cases passed. Results: {out_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
