"""M033-A: read-only, loopback-only Ollama inventory for upcoming M032 baselines.

This module deliberately does not call /api/chat, /api/generate or Ollama
management APIs: no model inference, downloads, loads or unloads.
Run from the backend directory:
    python -m eval.m033_inventory
    python -m eval.m033_inventory --json-out path/to/temporary-inventory.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.analysis.local_profiles import CURATED_PROFILES

_MAX_RESPONSE_BYTES = 1_000_000
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_SCHEMA_VERSION = "m033-a.1"


def validated_origin(raw_url: str) -> str:
    """Only literal loopback hosts. Reject userinfo, fragments and URL paths."""
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("M033-A inventory permits only explicit loopback HTTP(S) URLs")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Userinfo is not allowed in an inventory endpoint")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Inventory URL must be a bare Ollama origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid inventory port") from exc
    if not port:
        raise ValueError("Inventory URL requires an explicit port")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{parsed.scheme}://{host}:{port}"


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow a loopback server's redirect to any other destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise ValueError("M033-A inventory refuses HTTP redirects")


def _safe_opener() -> urllib.request.OpenerDirector:
    # Ignore proxy settings for direct loopback-only metadata requests.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())


def _request_json(origin: str, route: str, payload: dict[str, str] | None = None) -> dict[str, Any]:
    """Bounded HTTP request; only constant, read-only metadata routes allowed."""
    safe_origin = validated_origin(origin)
    if route not in ("/api/tags", "/api/ps", "/api/show"):
        raise ValueError("Only Ollama metadata endpoints are allowed")
    if route == "/api/show":
        if payload is None or set(payload) != {"model"} or not payload["model"]:
            raise ValueError("A model is required for /api/show")
    elif payload is not None:
        raise ValueError("GET metadata endpoints do not take a body")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        safe_origin + route,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with _safe_opener().open(request, timeout=6) as response:
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ValueError("Ollama metadata response exceeds the size limit")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError(f"Unexpected JSON object from {route}")
    return decoded


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        v = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return v if v >= 0 else None


def collect_inventory(origin: str, *, observed_at: str | None = None) -> dict[str, Any]:
    """Return observed server metadata and warnings, never estimated performance."""
    safe_origin = validated_origin(origin)  # reject before any network traffic
    tags = _request_json(safe_origin, "/api/tags")
    models = tags.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama /api/tags did not supply a models array")
    warnings: list[str] = []
    active_observed = False
    try:
        active = _request_json(safe_origin, "/api/ps")
        active_rows = active.get("models")
        if not isinstance(active_rows, list):
            active_rows = []
            warnings.append("Unexpected /api/ps format; active model status is unknown.")
        else:
            active_observed = True
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        active_rows = []
        warnings.append(f"/api/ps unavailable ({type(exc).__name__}); active status is unknown.")

    resident = {
        _text(row.get("name") or row.get("model")): row
        for row in active_rows if isinstance(row, dict)
    }
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in models:
        if not isinstance(row, dict):
            warnings.append("Skipped invalid /api/tags model entry.")
            continue
        name = _text(row.get("name") or row.get("model"))
        if not name or name in seen:
            warnings.append("Skipped model entry with empty or duplicate name.")
            continue
        seen.add(name)
        details = row.get("details")
        details = details if isinstance(details, dict) else {}
        # Exact profile only: the production resolver's family-name fallback
        # is not evidence that another model size/variant was benchmarked.
        profile = CURATED_PROFILES.get(name)
        try:
            show = _request_json(safe_origin, "/api/show", {"model": name})
            raw_caps = show.get("capabilities", [])
            advertised_caps = sorted({
                c.strip().lower()
                for c in raw_caps if isinstance(c, str) and c.strip()
            }) if isinstance(raw_caps, list) else []
            if not isinstance(raw_caps, list):
                warnings.append(f"{name}: unexpected /api/show capabilities format.")
            show_ok = True
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            show_ok = False
            advertised_caps = []
            warnings.append(f"{name}: /api/show failed ({type(exc).__name__}); capabilities unknown.")
        live = resident.get(name)
        records.append({
            "name": name,
            "disk_bytes": _safe_int(row.get("size")),
            "parameter_size_reported": _text(details.get("parameter_size")),
            "quantization_reported": _text(details.get("quantization_level")),
            "advertised_capabilities": advertised_caps,
            "capabilities_observed": show_ok,
            "running_now": (live is not None) if active_observed else None,
            "loaded_bytes_reported": _safe_int(live.get("size")) if live else None,
            "vram_bytes_reported": _safe_int(live.get("size_vram")) if live else None,
            "curated_profile": profile is not None,
            "profile_performance_class": profile.perf_class if profile else "unknown",
            "workstation_only": profile.perf_class == "workstation-only" if profile else None,
            "possible_vision": "vision" in advertised_caps,
            "note": "No performance, quality, safety, or routing verdict can be inferred from metadata.",
        })
    return {
        "schema_version": _SCHEMA_VERSION,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "endpoint": safe_origin,
        "inventory_type": "read_only_metadata_not_a_benchmark",
        "installed_count": len(records),
        "models": records,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M033-A: safe, read-only Ollama model inventory")
    parser.add_argument("--origin", default="http://127.0.0.1:11434")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        report = collect_inventory(args.origin)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"M033 inventory unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"M033-A inventory: {report['installed_count']} installed models at {report['endpoint']}")
    for item in report["models"]:
        print(
            f"  {item['name']}: caps={','.join(item['advertised_capabilities']) or '?'} "
            f"curated={item['curated_profile']} perf={item['profile_performance_class']} "
            f"running={item['running_now']}"
        )
    for warning in report["warnings"]:
        print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
