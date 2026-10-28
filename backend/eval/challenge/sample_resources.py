"""M018 resource sampler: process memory + CPU during local inference.

Samples Ollama + FieldRook backend RSS every second to JSONL. No model
calls itself; run it alongside a challenge run or a single investigation.
Usage: python eval/challenge/sample_resources.py --out <file> --seconds <n>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone


def snapshot() -> list[dict]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'ollama|python|node' } | "
         "Select-Object ProcessId, Name, WorkingSetSize, UserModeTime, KernelModeTime, CommandLine | "
         "ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=30,
    )
    try:
        rows = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(rows, dict):
        rows = [rows]
    procs = []
    for row in rows:
        cmd = str(row.get("CommandLine") or "")
        name = str(row.get("Name", ""))
        keep = (
            "ollama" in name.lower()  # server + llama-server runner processes
            or "fieldrook" in cmd.lower()
            or "uvicorn" in cmd.lower()
            or "vite" in cmd.lower()
        )
        if not keep:
            continue
        procs.append({
            "pid": row.get("ProcessId"),
            "name": name,
            "rss_mb": round((row.get("WorkingSetSize") or 0) / 1e6, 1),
            "cmd": cmd[:160],
        })
    return procs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample Ollama/FieldRook resources")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    end = time.monotonic() + args.seconds
    with open(args.out, "w", encoding="utf-8") as handle:
        while time.monotonic() < end:
            stamp = datetime.now(timezone.utc).isoformat()
            handle.write(json.dumps({"t": stamp, "procs": snapshot()}) + "\n")
            handle.flush()
            time.sleep(1.0)
    print(f"samples: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
