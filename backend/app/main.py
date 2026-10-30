"""FieldRook API entrypoint (+ single-process desktop server, M025 BETA).

Dev mode (no ``frontend/dist``): pure JSON API, ``GET /`` returns the tagline.
Desktop mode (dist present — ``frontend/dist`` in dev, bundled
``frontend-dist`` when frozen): the same uvicorn process also serves the
built UI at ``/`` via ``StaticFiles(html=True)`` mounted AFTER all ``/api/*``
routers, and ``GET /`` serves ``index.html``. ``/api/status`` is THE health
signal in both modes.

Desktop runtime helpers (bind config, port probe, instance-lock protocol)
live here so the frozen entry point (``packaging/desktop/``), the launcher,
and the ``test_desktop_*`` suite share one implementation.
"""

from __future__ import annotations

import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .paths import frontend_dist_dir, is_frozen, lock_file
from .routers import actions, collector_import, incidents, investigations, knowledge, resolutions, services
from .security import LOCAL_HOSTS, LocalOriginMiddleware
from .version import get_version

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
# Hosts uvicorn may bind in the desktop runtime. Anything else is refused at
# startup: the app is localhost-only by contract, no silent LAN exposure.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from .investigations import persistence

    stuck = persistence.fail_stuck_executions()
    if stuck:
        print(f"FieldRook: marked {stuck} interrupted action(s) as failed.")
    yield


def trusted_hosts() -> list[str]:
    """Hosts accepted by TrustedHostMiddleware (DNS-rebinding guard).

    Dev/test additionally allow ``testserver`` (Starlette TestClient's
    default Host; unroutable, so it weakens nothing real). Frozen builds
    are strict localhost-only.
    """
    hosts = set(LOCAL_HOSTS)
    if not is_frozen():
        hosts.add("testserver")
    return sorted(hosts)


def create_app(dist_dir: Path | str | bool | None = None) -> FastAPI:
    """Build the FastAPI app; ``dist_dir`` override exists for tests.

    ``None`` (default) auto-detects via :func:`paths.frontend_dist_dir`;
    pass ``False`` to force dev-API mode, or a directory to force UI mode.
    """
    if dist_dir is None:
        resolved: Path | None = frontend_dist_dir()
    elif dist_dir is False:
        resolved = None
    else:
        candidate = Path(dist_dir)
        resolved = candidate if (candidate / "index.html").is_file() else None

    application = FastAPI(
        title="FieldRook API",
        version=get_version(),
        description="Evidence-driven troubleshooting: Diagnose. Verify. Resolve.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.add_middleware(LocalOriginMiddleware)
    # Added last -> runs first (outermost): reject off-host before anything else.
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts())

    application.include_router(services.router)
    application.include_router(incidents.router)
    application.include_router(investigations.router)
    application.include_router(actions.router)
    application.include_router(collector_import.router)
    application.include_router(resolutions.router)
    application.include_router(knowledge.router)

    @application.get("/")
    def read_root() -> Any:
        if resolved is not None:
            return FileResponse(resolved / "index.html")
        return {"name": "FieldRook", "tagline": "Diagnose. Verify. Resolve."}

    if resolved is not None:
        # AFTER all /api/* routers: API routes match first, the UI serves /.
        application.mount("/", StaticFiles(directory=resolved, html=True), name="frontend")

    return application


app = create_app()


# --------------------------------------------------------------------------
# Desktop bind config (FIELDROOK_PORT / FIELDROOK_HOST + loopback refusal)
# --------------------------------------------------------------------------


def resolve_port() -> int:
    """Listen port: ``FIELDROOK_PORT`` override, default 8000. Never silent."""
    raw = os.environ.get("FIELDROOK_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(raw)
    except ValueError:
        raise RuntimeError(f"Invalid FIELDROOK_PORT {raw!r}: expected 1-65535.") from None
    if not 1 <= port <= 65535:
        raise RuntimeError(f"Invalid FIELDROOK_PORT {raw!r}: expected 1-65535.")
    return port


def resolve_host() -> str:
    """Listen host: loopback only; any non-loopback bind is refused loudly."""
    host = os.environ.get("FIELDROOK_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            f"Refusing non-loopback bind {host!r}: FieldRook is localhost-only "
            "(allowed: 127.0.0.1, localhost, ::1)."
        )
    return host


def is_port_in_use(host: str, port: int, timeout_s: float = 1.0) -> bool:
    """True when something already accepts TCP on host:port (port probe)."""
    family = socket.AF_INET6 if ":" in host.strip("[]") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            return sock.connect_ex((host.strip("[]"), port)) == 0
    except OSError:
        return False


# --------------------------------------------------------------------------
# Single-instance lock protocol (file format shared with the launcher)
# --------------------------------------------------------------------------


def write_instance_lock(pid: int | None = None, port: int | None = None) -> Path:
    """Write our lock file; returns its path. Launcher-owned in production."""
    path = lock_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid if pid is not None else os.getpid(),
        "port": port if port is not None else resolve_port(),
        "service": "fieldrook-api",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def read_instance_lock() -> dict[str, Any] | None:
    """Read the lock file; None when absent or corrupt (treat as stale)."""
    try:
        data = json.loads(lock_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def pid_is_alive(pid: object) -> bool:
    """True when pid names a live process (portable existence check)."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # exists, just not ours to signal
    except (OSError, ValueError):
        return False
    return True


def lock_holder_is_live(lock: dict[str, Any] | None = None) -> bool:
    """True when the lock names a live PID (stale locks must be replaced)."""
    if lock is None:
        lock = read_instance_lock()
    if not lock:
        return False
    return pid_is_alive(lock.get("pid"))


# --------------------------------------------------------------------------
# Server entry (used by the frozen exe AND `python -m` dev runs)
# --------------------------------------------------------------------------


def run() -> None:
    """Validate bind config, then serve forever under uvicorn (blocking)."""
    import uvicorn

    from .paths import logs_dir

    host = resolve_host()  # raises on non-loopback: refuse before binding
    port = resolve_port()
    if is_port_in_use(host, port):
        raise RuntimeError(
            f"Port {port} on {host} is already in use — another FieldRook "
            "instance (or another app) is running. Stop it or set "
            "FIELDROOK_PORT to a free port."
        )
    try:
        logs_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # logging dir is best-effort; the launcher also captures output
    print(f"FieldRook {get_version()}: serving on http://{host}:{port}/", flush=True)
    uvicorn.run(app, host=host, port=port)
