"""Targeted, bounded Windows event-log searches (read-only).

Every search reports what it actually did: how many entries were examined,
which time window was queried, whether the query completed, how many entries
matched, and which limits applied. Zero matches is reported as an observation,
never as proof that no failure exists.
"""

from __future__ import annotations

from .windows_tools import (  # same package: reuse the allowlisted runner
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

ALLOWED_LOGS = ("System", "Application")
SCAN_CAP = 200
MAX_EVENT_MESSAGE_CHARS = 500


def normalize_logs(logs: list[str]) -> list[str]:
    """Validate requested log names against the allowlist (case-insensitive)."""
    canonical: list[str] = []
    for log in logs:
        match = next((allowed for allowed in ALLOWED_LOGS if allowed.lower() == str(log).lower()), None)
        if match is None:
            raise ValueError(f"Unsupported event log {log!r}: expected System or Application.")
        if match not in canonical:
            canonical.append(match)
    if not canonical:
        raise ValueError("At least one event log must be requested.")
    return canonical


_EVENTS_SCRIPT_TEMPLATE = (
    "Get-WinEvent -FilterHashtable @{LogName='{log}'; Level=1,2,3; "
    "StartTime=(Get-Date).AddHours(-{hours})} -MaxEvents {cap} -ErrorAction SilentlyContinue "
    "| Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message "
    "| ConvertTo-Json -Compress -Depth 3"
)


def _matches(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords if keyword)


def _summarize_entry(entry: dict) -> dict:
    return {
        "time_created": str(entry.get("TimeCreated", "")),
        "id": entry.get("Id"),
        "level": str(entry.get("LevelDisplayName", "")),
        "provider": str(entry.get("ProviderName", "")),
        "message": str(entry.get("Message", ""))[:MAX_EVENT_MESSAGE_CHARS],
    }


def search_events_live(
    keywords: list[str],
    logs: list[str],
    hours: int,
    max_events: int,
    timeout_s: float,
) -> dict:
    """Search live event logs. Returns per-log statistics plus bounded matches."""
    canonical = normalize_logs(logs)
    results: list[dict] = []
    for log in canonical:
        source = f"powershell:Get-WinEvent {log}"
        script = _EVENTS_SCRIPT_TEMPLATE.replace("{log}", log).replace(
            "{hours}", str(hours)
        ).replace("{cap}", str(SCAN_CAP))
        try:
            payload = _run_powershell(script, source, timeout_s)
            entries = _as_dict_list(payload, source)
        except (DiagnosticCommandError, ValueError) as exc:
            results.append(
                {
                    "log": log,
                    "completed": False,
                    "error": str(exc),
                    "scanned": 0,
                    "matched": 0,
                    "events": [],
                    "note": "Log query failed; no entries were examined.",
                }
            )
            continue
        matched_all = [
            _summarize_entry(entry)
            for entry in entries
            if _matches(f"{entry.get('ProviderName', '')} {entry.get('Message', '')}", keywords)
        ]
        results.append(
            {
                "log": log,
                "completed": True,
                "scanned": len(entries),
                "matched": len(matched_all),
                "events": matched_all[:max_events],
                "note": (
                    f"Examined {len(entries)} entries (Levels 1-3, last {hours}h, "
                    f"scan capped at {SCAN_CAP}); showing {min(len(matched_all), max_events)} "
                    f"of {len(matched_all)} matches. Absence of matches does not prove "
                    "absence of failure."
                ),
            }
        )
    return {
        "window_hours": hours,
        "levels": [1, 2, 3],
        "scan_cap": SCAN_CAP,
        "keywords": keywords,
        "logs": results,
    }
