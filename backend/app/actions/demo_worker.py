"""Application-owned demo worker: health checks and fenced lifecycle.

The demo worker is the ONLY component FieldRook may ever change, and only
through the predefined recovery action. Process operations are fenced twice:
a pid is touched only when its live command line proves it is the demo
worker script, and spawning uses a fixed argv (this repo's worker.py).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ..paths import WORKER_EXE_NAME, default_demo_state_dir, worker_command, worker_script_path

HEARTBEAT_MAX_AGE_S = 10.0
WORKER_ID = "demo-worker"


class WorkerError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def state_dir() -> Path:
    # Override wins; frozen defaults to the user data dir (never the dev checkout).
    return default_demo_state_dir()


def worker_script() -> Path:
    """Demo worker `.py` script (M025: `FIELDROOK_WORKER_SCRIPT` override).

    Kept for direct `[sys.executable, script]` spawns (tests, dev). Frozen
    bundles spawn the worker exe instead — see `spawn_worker()`.
    """
    return worker_script_path()


def read_health() -> dict[str, Any]:
    """Read-only health check. Never raises; unknown states are data."""
    heartbeat_path = state_dir() / "heartbeat.json"
    try:
        raw = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "worker_id": WORKER_ID,
            "status": "unknown",
            "detail": "No heartbeat yet (worker may not be running).",
        }
    except (OSError, ValueError) as exc:
        return {
            "worker_id": WORKER_ID,
            "status": "unknown",
            "detail": f"Heartbeat unreadable: {exc}",
        }
    if not isinstance(raw, dict):
        return {"worker_id": WORKER_ID, "status": "unknown", "detail": "Heartbeat malformed."}
    try:
        age = time.time() - float(raw.get("updated_at", 0))
    except (TypeError, ValueError):
        age = None
    result: dict[str, Any] = {
        "worker_id": raw.get("worker_id", WORKER_ID),
        "status": raw.get("status", "unknown"),
        "pid": raw.get("pid"),
        "detail": raw.get("detail", ""),
        "updated_at": raw.get("updated_at"),
        "heartbeat_age_s": age,
        "process_verified": False,
    }
    pid = raw.get("pid")
    result["process_verified"] = is_own_worker_process(pid)
    if age is None or age > HEARTBEAT_MAX_AGE_S:
        result["status"] = "unknown"
        result["detail"] = (
            f"Heartbeat stale ({'?' if age is None else f'{age:.0f}s'} old; "
            f"worker may have stopped). Last reported: {raw.get('status')}."
        )
    return result


def write_control(mode: str) -> None:
    if mode not in ("healthy", "failing"):
        raise WorkerError(f"Invalid worker mode {mode!r}.")
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "control.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")


def _pid_cmdline(pid: int) -> str | None:
    if os.name != "nt":
        return None
    if not isinstance(pid, int) or pid <= 0:
        return None
    from ..diagnostics.windows_tools import _run_powershell  # reuse allowlisted runner

    script = (
        f"Get-CimInstance -ClassName Win32_Process -Filter \"ProcessId={pid}\" "
        "| Select-Object -ExpandProperty CommandLine"
    )
    try:
        output = _run_powershell(script, "powershell:Get-CimInstance Win32_Process", 10.0)
    except Exception:
        return None
    return output.strip() or None


def is_own_worker_process(pid: object) -> bool:
    """True only when the live command line proves pid is our worker.

    Accepts the dev `.py` spawn AND the frozen worker exe (same fence:
    the exact bundled exe name must appear in the live command line).
    """
    if not isinstance(pid, int) or pid <= 0 or isinstance(pid, bool):
        return False
    cmdline = _pid_cmdline(pid)
    if not cmdline:
        return False
    lowered = cmdline.lower()
    if "demo_worker" in lowered and "worker.py" in lowered:
        return True
    return WORKER_EXE_NAME.lower() in lowered


def terminate_verified_worker(pid: int) -> None:
    if not is_own_worker_process(pid):
        raise WorkerError(f"Refusing to terminate pid {pid}: not the verified demo worker.")
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkerError(f"Could not terminate worker pid {pid}: {exc}") from exc
    if completed.returncode != 0 and "not found" not in (completed.stderr or "").lower():
        raise WorkerError(f"taskkill failed: {(completed.stderr or completed.stdout).strip()[:200]}")


def spawn_worker() -> int:
    # M025: frozen bundles have no interpreter, so this spawns the bundled
    # worker exe there; dev keeps [sys.executable, worker.py]. Detached by
    # design — the desktop launcher stops it via terminate_verified_worker.
    command = worker_command()
    target = Path(command[-1])
    if not target.is_file():
        raise WorkerError("Demo worker script is missing.")
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_handle = open(directory / "worker.log", "a", encoding="utf-8")
    try:
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        proc = subprocess.Popen(
            command,
            cwd=str(target.parent if target.suffix.lower() == ".py" else directory),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
            start_new_session=(os.name != "nt"),
        )
    finally:
        log_handle.close()
    return proc.pid


def wait_for_health(status: str, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last = read_health()
    while time.time() < deadline:
        last = read_health()
        if last.get("status") == status:
            return last
        time.sleep(1.0)
    return last


def recover() -> dict[str, Any]:
    """Predefined recovery: restore healthy config; restart only if not running."""
    before = read_health()
    write_control("healthy")
    healthy = wait_for_health("healthy", 12.0)
    if healthy.get("status") == "healthy":
        return {"restarted": False, "before": before, "after": healthy}
    pid = before.get("pid")
    if isinstance(pid, int) and is_own_worker_process(pid):
        terminate_verified_worker(pid)
    new_pid = spawn_worker()
    after = wait_for_health("healthy", 15.0)
    after["restarted_pid"] = new_pid
    return {"restarted": True, "before": before, "after": after}


def verify_healthy() -> tuple[bool, dict[str, Any]]:
    """Independent verification: fresh health read, trusts nothing else."""
    after = read_health()
    return (after.get("status") == "healthy", after)
