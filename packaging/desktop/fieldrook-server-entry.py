"""Frozen server entry point (M025 BETA desktop runtime).

PyInstaller target for `FieldRook-Server.exe` (one-dir). Also runnable
unfrozen (`python packaging/desktop/fieldrook-server-entry.py ...`) for
smoke tests — it adds `backend/` to `sys.path` when not frozen.

Commands:
  serve               start the API+UI server (default; honors FIELDROOK_PORT)
  --version           print the release version and exit 0
  --stop-demo-worker  terminate the verified detached demo worker, if any
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_backend_importable() -> None:
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        return
    backend = Path(__file__).resolve().parents[2] / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))


_ensure_backend_importable()


def cmd_serve() -> int:
    from app.main import run

    try:
        run()
    except RuntimeError as exc:
        _log_startup_error(str(exc))
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


def cmd_version() -> int:
    from app.version import get_version

    print(get_version())
    return 0


def cmd_stop_demo_worker() -> int:
    """Fenced shutdown of the detached demo worker (launcher calls this)."""
    from app.actions import demo_worker

    health = demo_worker.read_health()
    pid = health.get("pid")
    if not isinstance(pid, int) or not demo_worker.is_own_worker_process(pid):
        print("demo worker: not running (no verified worker process).")
        return 0
    try:
        demo_worker.terminate_verified_worker(pid)
    except demo_worker.WorkerError as exc:
        print(f"demo worker: stop failed: {exc}")
        return 1
    print(f"demo worker: stopped pid {pid}.")
    return 0


def _log_startup_error(message: str) -> None:
    """Startup errors must be visible AND logged (M025 toolchain contract)."""
    print(f"FieldRook: startup failed: {message}", flush=True)
    try:
        from app.paths import logs_dir

        directory = logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / "server.err.log", "a", encoding="utf-8") as handle:
            handle.write(f"startup failed: {message}\n")
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="FieldRook-Server", description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--version", action="store_true", help="print release version")
    group.add_argument(
        "--stop-demo-worker",
        action="store_true",
        help="stop the verified detached demo worker and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        return cmd_version()
    if args.stop_demo_worker:
        return cmd_stop_demo_worker()
    return cmd_serve()


if __name__ == "__main__":
    raise SystemExit(main())
