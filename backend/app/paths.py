"""Frozen-aware path resolution for the FieldRook desktop runtime (M025 BETA).

This is the ONE place that knows the difference between a source checkout
(dev) and a PyInstaller one-dir bundle (frozen):

- dev:    paths resolve into the repo checkout (``bundle_dir()`` == repo root).
- frozen: read-only payload resolves into ``sys._MEIPASS`` (the bundle dir),
  while ALL writable state (DB, demo state, logs, lock, .env) resolves into
  the per-user data dir (``%LOCALAPPDATA%\\FieldRook`` on Windows).

Hard rules (M025 contracts):

- Never default to or migrate the dev database: frozen defaults point at the
  user data dir, never at a checkout.
- Explicit env overrides (``FIELDROOK_DB_PATH``, ``FIELDROOK_DEMO_STATE``,
  ``FIELDROOK_WORKER_SCRIPT``, ``FIELDROOK_ENV_FILE``) always win, frozen or
  dev, so tests and operators keep full control.

Stdlib only: safe to import from anywhere, including the frozen entry point.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FieldRook"
WORKER_EXE_NAME = "fieldrook-demo-worker.exe"
WORKER_BUNDLE_SUBDIR = "demo-worker"
FRONTEND_BUNDLE_SUBDIR = "frontend-dist"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def bundle_dir() -> Path:
    """Read-only application payload dir.

    Frozen: ``sys._MEIPASS`` (the one-dir ``_internal`` folder). Dev: the
    repo root (``backend/app/paths.py`` -> parents[2]).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if is_frozen():  # pragma: no cover - defensive: frozen without _MEIPASS
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def exe_dir() -> Path:
    """Directory holding the running executable (frozen) or repo root (dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_dir()


def user_data_dir() -> Path:
    """Per-user writable data dir (DB, demo state, logs, lock live here)."""
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def logs_dir() -> Path:
    """User data log dir (M025: startup/shutdown errors visible AND logged)."""
    return user_data_dir() / "logs"


def lock_file() -> Path:
    """Single-instance lock file (launcher-owned protocol, see main.py)."""
    return user_data_dir() / "fieldrook.lock"


def default_db_path() -> Path:
    """SQLite path: override wins; frozen -> user data; dev -> checkout."""
    override = os.environ.get("FIELDROOK_DB_PATH", "").strip()
    if override:
        return Path(override)
    if is_frozen():
        return user_data_dir() / "fieldrook.db"
    return bundle_dir() / "backend" / "data" / "fieldrook.db"


def default_demo_state_dir() -> Path:
    """Demo worker state dir: override wins; frozen -> user data; dev -> repo."""
    override = os.environ.get("FIELDROOK_DEMO_STATE", "").strip()
    if override:
        return Path(override)
    if is_frozen():
        return user_data_dir() / "demo-state"
    return bundle_dir() / "demo_worker" / "state"


def worker_script_path() -> Path:
    """Demo worker ``.py`` script (dev path, override-aware).

    Frozen bundles ship the worker as a separate exe (no interpreter in the
    bundle can run ``.py``); use :func:`worker_command` for spawning.
    """
    override = os.environ.get("FIELDROOK_WORKER_SCRIPT", "").strip()
    if override:
        return Path(override)
    return bundle_dir() / "demo_worker" / "worker.py"


def worker_exe_path() -> Path:
    """Frozen demo worker exe, bundled as data inside the server one-dir."""
    return bundle_dir() / WORKER_BUNDLE_SUBDIR / WORKER_EXE_NAME


def worker_command() -> list[str]:
    """Spawn argv for the demo worker, dev- and frozen-aware.

    - ``FIELDROOK_WORKER_SCRIPT`` override: ``.exe`` runs directly, anything
      else runs under the current interpreter.
    - frozen: the bundled worker exe (runs directly, no interpreter).
    - dev: ``[sys.executable, demo_worker/worker.py]`` (unchanged behavior).
    """
    override = os.environ.get("FIELDROOK_WORKER_SCRIPT", "").strip()
    if override:
        if override.lower().endswith(".exe"):
            return [override]
        return [sys.executable, override]
    if is_frozen():
        return [str(worker_exe_path())]
    return [sys.executable, str(bundle_dir() / "demo_worker" / "worker.py")]


def frontend_dist_dir() -> Path | None:
    """Built frontend (``index.html`` + assets) or None when absent.

    Frozen: ``<bundle>/frontend-dist`` (PyInstaller data). Dev: the repo's
    ``frontend/dist`` (present after ``pnpm run build``).
    """
    candidate = bundle_dir() / FRONTEND_BUNDLE_SUBDIR if is_frozen() else bundle_dir() / "frontend" / "dist"
    if (candidate / "index.html").is_file():
        return candidate
    return None


def version_file() -> Path:
    """Single-sourced release version file (repo root / bundled data)."""
    return bundle_dir() / "VERSION"


def dotenv_path() -> Path:
    """``.env`` location: explicit override wins; frozen NEVER reads repo root.

    Frozen loads the per-user ``%LOCALAPPDATA%\\FieldRook\\.env`` (absent by
    default — the desktop app ships no secrets). Dev keeps the repo-root
    ``.env`` for operator convenience.
    """
    explicit = os.environ.get("FIELDROOK_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit)
    if is_frozen():
        return user_data_dir() / ".env"
    return bundle_dir() / ".env"


def collector_search_path() -> Path:
    """Dir to add to ``sys.path`` ONLY if ``import collector`` fails.

    Frozen: the bundle dir (collector shipped as bundled data). Dev: the repo
    root (collector is a standalone stdlib package at the repo root).
    """

    return bundle_dir()
