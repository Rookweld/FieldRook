"""Desktop single-instance + bind config (M025 BETA).

Covers `app.main` bind resolution (`FIELDROOK_PORT`/`FIELDROOK_HOST` +
loopback refusal), the TCP port probe, and the lock-file protocol shared
with `packaging/desktop/FieldRook-Launcher.ps1`, including live launcher
probe runs (`-CheckOnly`) when PowerShell is available.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app import main as app_main
from app.main import (
    is_port_in_use,
    lock_holder_is_live,
    pid_is_alive,
    read_instance_lock,
    resolve_host,
    resolve_port,
    write_instance_lock,
)

REPO_ROOT = Path(app_main.__file__).resolve().parents[2]
LAUNCHER_PS1 = REPO_ROOT / "packaging" / "desktop" / "FieldRook-Launcher.ps1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_resolve_port_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIELDROOK_PORT", raising=False)
    assert resolve_port() == 8000
    monkeypatch.setenv("FIELDROOK_PORT", "8123")
    assert resolve_port() == 8123


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "65536", "", "  ", "8O00"])
def test_resolve_port_rejects_garbage(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv("FIELDROOK_PORT", bad)
    with pytest.raises(RuntimeError, match="FIELDROOK_PORT"):
        resolve_port()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "[::1]"])
def test_resolve_host_allows_loopback(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    monkeypatch.setenv("FIELDROOK_HOST", host)
    assert resolve_host() == host


def test_resolve_host_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIELDROOK_HOST", raising=False)
    assert resolve_host() == "127.0.0.1"
    monkeypatch.setenv("FIELDROOK_HOST", "  ")
    assert resolve_host() == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "8.8.8.8", "192.168.1.1", "example.com", "::"])
def test_resolve_host_refuses_non_loopback(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    """M025 security contract: startup refusal of non-loopback bind."""
    monkeypatch.setenv("FIELDROOK_HOST", host)
    with pytest.raises(RuntimeError, match="non-loopback"):
        resolve_host()


def test_is_port_in_use() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = int(listener.getsockname()[1])
        assert is_port_in_use("127.0.0.1", port) is True
    finally:
        listener.close()
    assert is_port_in_use("127.0.0.1", port) is False


def test_pid_is_alive_edges() -> None:
    assert pid_is_alive(os.getpid()) is True
    assert pid_is_alive(0) is False
    assert pid_is_alive(-1) is False
    assert pid_is_alive("1234") is False  # type: ignore[arg-type]
    assert pid_is_alive(True) is False


# PIDs this large are never assigned (real PIDs stay small); os.kill() on one
# deterministically reports "no such process" on Windows and POSIX alike.
UNASSIGNABLE_PID = 2**31 - 1


def _reaped_pid() -> int:
    """PID of a real dead process, with every handle to it already closed.

    Windows reports a dead process as ALIVE to ``os.kill(pid, 0)`` while
    ANY handle to it is still open — including the test's own Popen
    handle (proven: raw OpenProcess succeeds post-reap with exit code 0
    while a handle is held). So the spawn/wait must happen in this nested
    scope: only the bare pid escapes, and the Popen (plus its HANDLE) is
    gone before the caller asserts. Windows allocates PIDs from an
    incrementing counter, so the just-freed PID cannot be reassigned in
    the microseconds before the assertion runs.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    pid = proc.pid
    del proc  # close OUR handle: a held handle reads as "alive" on Windows
    return pid


def test_pid_is_alive_dead_process() -> None:
    assert pid_is_alive(_reaped_pid()) is False
    assert pid_is_alive(UNASSIGNABLE_PID) is False


def test_lock_roundtrip_and_corrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert read_instance_lock() is None
    path = write_instance_lock(pid=os.getpid(), port=8123)
    assert path == tmp_path / "FieldRook" / "fieldrook.lock"
    assert read_instance_lock() == {"pid": os.getpid(), "port": 8123, "service": "fieldrook-api"}
    assert lock_holder_is_live() is True
    path.write_text("{not json", encoding="utf-8")
    assert read_instance_lock() is None
    assert lock_holder_is_live() is False


def test_lock_holder_dead_pid_is_stale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    write_instance_lock(pid=_reaped_pid(), port=8123)
    assert lock_holder_is_live() is False
    write_instance_lock(pid=UNASSIGNABLE_PID, port=8123)
    assert lock_holder_is_live() is False


# --------------------------------------------------------------------------
# Live launcher probe runs (the real FieldRook-Launcher.ps1 -CheckOnly)
# --------------------------------------------------------------------------

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
needs_powershell = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")


def _check_only(port: int, data_dir: Path, timeout_s: float = 90.0) -> subprocess.CompletedProcess[str]:
    assert LAUNCHER_PS1.is_file(), f"launcher missing: {LAUNCHER_PS1}"
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(data_dir)
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER_PS1),
            "-CheckOnly",
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=str(REPO_ROOT),
        env=env,
    )


@needs_powershell
def test_launcher_probe_free_port_is_ready(tmp_path: Path) -> None:
    port = _free_port()
    # Hold the probe race shut: nothing listens on `port` right now.
    completed = _check_only(port, tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ready" in completed.stdout.lower()


@needs_powershell
def test_launcher_probe_occupied_port_is_conflict(tmp_path: Path) -> None:
    """A non-FieldRook listener is a port conflict, not 'already running'."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = int(listener.getsockname()[1])
        completed = _check_only(port, tmp_path)
    finally:
        listener.close()
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert "in use" in (completed.stdout + completed.stderr).lower()


class _StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/status":
            body = json.dumps({"service": "fieldrook-api", "model_mode": "simulated"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@needs_powershell
def test_launcher_probe_live_fieldrook_is_already_running(tmp_path: Path) -> None:
    """A /api/status that answers fieldrook-api means 'already running'."""
    server = HTTPServer(("127.0.0.1", 0), _StatusHandler)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        completed = _check_only(port, tmp_path)
    finally:
        server.shutdown()
        thread.join(timeout=10)
    assert completed.returncode == 3, completed.stdout + completed.stderr
    assert "already running" in (completed.stdout + completed.stderr).lower()
