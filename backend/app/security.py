"""Local-only request protections for the FieldRook backend.

The backend binds to localhost and serves a local UI. State-changing routes
must not be invocable by unrelated websites rendered in the technician's
browser. This middleware rejects browser-style mutation requests whose
Origin/Referer is not this machine.

M025 hardening: browsers always send ``Sec-Fetch-Site`` on fetch/form
requests and scripts cannot spoof it (forbidden header), so it closes the
headerless gap where a cross-site browser request arrives without
Origin/Referer. Rule order for mutating methods:

1. ``Sec-Fetch-Site`` present -> allow only ``same-origin``/``same-site``.
2. otherwise fall back to the Origin/Referer check; headerless requests are
   still allowed because non-browser clients (curl, TestClient, the desktop
   launcher's health probe) send neither header.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Sec-Fetch-Site values a same-machine page produces. Anything else present
# (cross-site, none, ...) on a mutation is a cross-site browser request.
SEC_FETCH_SITE_ALLOWED = frozenset({"same-origin", "same-site"})


def _host_of(value: str) -> str:
    try:
        return (urlsplit(value).hostname or "").lower()
    except ValueError:
        return ""


def is_local_origin_request(request: Request) -> bool:
    """Allow non-browser clients (no Origin/Referer) and local origins only."""
    site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if site:
        return site in SEC_FETCH_SITE_ALLOWED
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or referer
    if not candidate:
        return True
    return _host_of(candidate) in LOCAL_HOSTS


class LocalOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in MUTATING_METHODS and not is_local_origin_request(request):
            return JSONResponse(
                {"detail": "Cross-origin mutations are forbidden (local-only API)."},
                status_code=403,
            )
        return await call_next(request)
