"""FieldRook demo worker: application-owned background process for M003.

Writes a heartbeat file every 2 seconds. Reads demo_worker/state/control.json
each loop: {"mode": "healthy"} (default) or {"mode": "failing"} to simulate a
fault. Only FieldRook's predefined recovery action (or the simulate_failure
demo helper) changes its state; it never touches real services.

Run:  python demo_worker/worker.py   (foreground, ordinary user permissions)
"""

import json
import os
import sys
import time

STATE_DIR = os.environ.get(
    "FIELDROOK_DEMO_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"),
)
CONTROL_PATH = os.path.join(STATE_DIR, "control.json")
HEARTBEAT_PATH = os.path.join(STATE_DIR, "heartbeat.json")

WORKER_ID = "demo-worker"
VERSION = "0.3.0"


def read_mode() -> str:
    try:
        with open(CONTROL_PATH, encoding="utf-8") as handle:
            mode = json.load(handle).get("mode", "healthy")
    except (OSError, ValueError):
        return "healthy"
    return mode if mode in ("healthy", "failing") else "healthy"


def main() -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    started_at = time.time()
    pid = os.getpid()
    print(f"demo worker {WORKER_ID} started (pid={pid}, state={STATE_DIR})", flush=True)
    while True:
        mode = read_mode()
        status = "healthy" if mode == "healthy" else "failed"
        heartbeat = {
            "worker_id": WORKER_ID,
            "status": status,
            "pid": pid,
            "started_at": started_at,
            "updated_at": time.time(),
            "detail": "ok" if status == "healthy" else f"Simulated fault (mode={mode}).",
            "version": VERSION,
        }
        tmp_path = HEARTBEAT_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(heartbeat, handle)
        os.replace(tmp_path, HEARTBEAT_PATH)
        time.sleep(2.0)


if __name__ == "__main__":
    sys.exit(main())
