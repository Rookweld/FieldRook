"""Read-only local Microsoft Office diagnostics (BETA, new).

Read-only operations (proposed for the allowlist; LEAD adds them):

  O1. Get-ItemProperty Uninstall (Office products from both registry views)
  O2. Get-ItemProperty ClickToRun Configuration (C2R version + channel)

Reads installation metadata only: product names, versions, publisher,
channel. Never reads documents, mailboxes, credentials, or user content.
Nothing here changes system state. New allowlisted commands are proposed
by BETA via PROPOSED_ALLOWLIST_ADDITIONS and added by LEAD
(security-sensitive per FORGE_CONTRACTS.md section 3).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .windows_tools import (
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

PROPOSED_ALLOWLIST_ADDITIONS: tuple[str, ...] = (
    "Get-ItemProperty Uninstall/Office",
    "Get-ItemProperty ClickToRun/Configuration",
)

SOURCE_OFFICE_INSTALLS = "powershell:Get-ItemProperty Uninstall/Office"
SOURCE_OFFICE_C2R = "powershell:Get-ItemProperty ClickToRun/Configuration"

_INSTALLS_SCRIPT = (
    "(@(Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
    "-ErrorAction SilentlyContinue) + "
    "@(Get-ItemProperty HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
    "-ErrorAction SilentlyContinue)) "
    "| Where-Object { $_.DisplayName -like '*Office*' -or $_.DisplayName -like '*Microsoft 365*' } "
    "| Select-Object DisplayName,DisplayVersion,Publisher,InstallDate "
    "| ConvertTo-Json -Compress -Depth 3"
)
_C2R_SCRIPT = (
    "if (Test-Path HKLM:\\SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration) { "
    "Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration "
    "| Select-Object VersionToReport,ClientVersionToReport,ProductReleaseIds,Channel,InstallationPath "
    "| ConvertTo-Json -Compress -Depth 3 } else { '' }"
)


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListOfficeInstallsArgs(StrictArgs):
    """Args model for the proposed list_office_installs tool (lead reviews)."""


class GetOfficeConfigArgs(StrictArgs):
    """Args model for the proposed get_office_config tool (lead reviews)."""


def _summarize_install(entry: dict) -> dict[str, str]:
    return {
        "display_name": str(entry.get("DisplayName", "")),
        "display_version": str(entry.get("DisplayVersion", "") or ""),
        "publisher": str(entry.get("Publisher", "") or ""),
        "install_date": str(entry.get("InstallDate", "") or ""),
    }


def list_office_installs_live(timeout_s: float) -> list[dict[str, str]]:
    """List installed Office products from the uninstall registry (read-only).

    An empty list is a valid observation (Office not installed), never an
    error. Only product metadata is read; no user content is touched.
    """
    try:
        payload = _run_powershell(_INSTALLS_SCRIPT, SOURCE_OFFICE_INSTALLS, timeout_s)
    except DiagnosticCommandError as exc:
        raise DiagnosticCommandError(str(exc), SOURCE_OFFICE_INSTALLS) from exc
    installs = [_summarize_install(entry) for entry in _as_dict_list(payload, SOURCE_OFFICE_INSTALLS)]
    return [install for install in installs if install["display_name"]]


def _summarize_c2r(entry: dict) -> dict[str, Any]:
    release_ids = entry.get("ProductReleaseIds", "")
    if isinstance(release_ids, list):
        products = [str(item) for item in release_ids if str(item)]
    elif str(release_ids or "").strip():
        products = [part.strip() for part in str(release_ids).split(",") if part.strip()]
    else:
        products = []
    return {
        "installed": True,
        "version": str(entry.get("VersionToReport", "") or entry.get("ClientVersionToReport", "") or ""),
        "channel": str(entry.get("Channel", "") or ""),
        "products": products,
        "installation_path": str(entry.get("InstallationPath", "") or ""),
    }


def get_office_config_live(timeout_s: float) -> dict[str, Any]:
    """Read the Office Click-to-Run configuration (read-only).

    Returns {"installed": False} when the C2R key is absent (perpetual
    MSI install or no Office), which is a valid observation, not an error.
    """
    try:
        payload = _run_powershell(_C2R_SCRIPT, SOURCE_OFFICE_C2R, timeout_s)
    except DiagnosticCommandError as exc:
        raise DiagnosticCommandError(str(exc), SOURCE_OFFICE_C2R) from exc
    entries = _as_dict_list(payload, SOURCE_OFFICE_C2R)
    if not entries:
        return {"installed": False, "version": "", "channel": "", "products": [], "installation_path": ""}
    return _summarize_c2r(entries[0])


_FIXTURE_INSTALLS: list[dict[str, str]] = [
    {
        "display_name": "Microsoft 365 Apps for enterprise (fixture)",
        "display_version": "16.0.17231.20194",
        "publisher": "Microsoft Corporation",
        "install_date": "20240115",
    },
    {
        "display_name": "Microsoft Office Proofing Tools (fixture)",
        "display_version": "16.0.17231.20194",
        "publisher": "Microsoft Corporation",
        "install_date": "20240115",
    },
]

_FIXTURE_C2R: dict[str, Any] = {
    "installed": True,
    "version": "16.0.17231.20194",
    "channel": "Monthly Enterprise Channel (fixture)",
    "products": ["O365ProPlusRetail"],
    "installation_path": "C:\\Program Files\\Microsoft Office",
}


def list_office_installs_fixture() -> list[dict[str, str]]:
    """Deterministic mirror of list_office_installs_live over fixture data."""
    return [dict(install) for install in _FIXTURE_INSTALLS]


def get_fixture_office_installs() -> list[dict[str, str]]:
    return [dict(install) for install in _FIXTURE_INSTALLS]


def get_office_config_fixture() -> dict[str, Any]:
    """Deterministic mirror of get_office_config_live over fixture data."""
    record = dict(_FIXTURE_C2R)
    record["products"] = list(_FIXTURE_C2R["products"])
    return record


def get_fixture_office_config() -> dict[str, Any]:
    return get_office_config_fixture()


__all__ = [
    "PROPOSED_ALLOWLIST_ADDITIONS",
    "SOURCE_OFFICE_C2R",
    "SOURCE_OFFICE_INSTALLS",
    "GetOfficeConfigArgs",
    "ListOfficeInstallsArgs",
    "get_fixture_office_config",
    "get_fixture_office_installs",
    "get_office_config_fixture",
    "get_office_config_live",
    "list_office_installs_fixture",
    "list_office_installs_live",
]
