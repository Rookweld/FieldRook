"""Allowlisted Windows OS and network diagnostics.

Read-only operations (extending windows_tools):

  4. Get-CimInstance Win32_OperatingSystem (basic OS information)
  5. Get-NetAdapter (adapter status)
  6. Get-NetIPAddress (IP configuration)
  7. Get-DnsClientServerAddress (DNS configuration)
  8. Get-NetTCPConnection -State Established (bounded connection sample)

One narrowly bounded ACTIVE test:

  9. Resolve-DnsName (single A/AAAA lookup of a validated hostname)

The active test sends one DNS query and changes nothing. It is labeled
as an active test in tool descriptions and evidence provenance.
"""

from __future__ import annotations

import re
import time

from .windows_tools import (  # same package: reuse the allowlisted runner
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

SOURCE_OS = "powershell:Get-CimInstance Win32_OperatingSystem"
SOURCE_ADAPTERS = "powershell:Get-NetAdapter"
SOURCE_IP = "powershell:Get-NetIPAddress"
SOURCE_DNS = "powershell:Get-DnsClientServerAddress"
SOURCE_CONNECTIONS = "powershell:Get-NetTCPConnection Established"

_OS_SCRIPT = (
    "Get-CimInstance -ClassName Win32_OperatingSystem "
    "| Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime,WindowsDirectory "
    "| ConvertTo-Json -Compress -Depth 3"
)
_ADAPTERS_SCRIPT = (
    "Get-NetAdapter "
    "| Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress,InterfaceIndex "
    "| ConvertTo-Json -Compress -Depth 3"
)
_IP_SCRIPT = (
    "Get-NetIPAddress "
    "| Select-Object InterfaceAlias,IPAddress,PrefixLength,AddressFamily,PrefixOrigin,SuffixOrigin "
    "| ConvertTo-Json -Compress -Depth 3"
)
_DNS_SCRIPT = (
    "Get-DnsClientServerAddress "
    "| Select-Object InterfaceAlias,ServerAddresses "
    "| ConvertTo-Json -Compress -Depth 3"
)
_CONNECTIONS_SCRIPT = (
    "Get-NetTCPConnection -State Established "
    "| Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess "
    "| ConvertTo-Json -Compress -Depth 3"
)
SOURCE_RESOLVE = "powershell:Resolve-DnsName"
_RESOLVE_SCRIPT_TEMPLATE = (
    "Resolve-DnsName -Name '{hostname}' -Type A_AAAA -DnsOnly "
    "-ErrorAction Stop "
    "| Select-Object Name,Type,IPAddress,Section "
    "| ConvertTo-Json -Compress -Depth 3"
)
_HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?$"
)


def get_os_info_live(timeout_s: float) -> dict:
    payload = _run_powershell(_OS_SCRIPT, SOURCE_OS, timeout_s)
    entries = _as_dict_list(payload, SOURCE_OS)
    if not entries:
        raise DiagnosticCommandError("No Win32_OperatingSystem record returned.", SOURCE_OS)
    entry = entries[0]
    return {
        "caption": str(entry.get("Caption", "")),
        "version": str(entry.get("Version", "")),
        "build_number": str(entry.get("BuildNumber", "")),
        "os_architecture": str(entry.get("OSArchitecture", "")),
        "last_boot_up_time": str(entry.get("LastBootUpTime", "")),
        "windows_directory": str(entry.get("WindowsDirectory", "")),
    }


def get_adapters_live(timeout_s: float, limit: int) -> list[dict]:
    payload = _run_powershell(_ADAPTERS_SCRIPT, SOURCE_ADAPTERS, timeout_s)
    adapters = []
    for entry in _as_dict_list(payload, SOURCE_ADAPTERS):
        adapters.append(
            {
                "name": str(entry.get("Name", "")),
                "description": str(entry.get("InterfaceDescription", "")),
                "status": str(entry.get("Status", "")),
                "link_speed": str(entry.get("LinkSpeed", "")),
                "mac_address": str(entry.get("MacAddress", "")),
                "interface_index": entry.get("InterfaceIndex"),
            }
        )
    return [adapter for adapter in adapters if adapter["name"]][:limit]


def get_ip_config_live(timeout_s: float, limit: int) -> list[dict]:
    payload = _run_powershell(_IP_SCRIPT, SOURCE_IP, timeout_s)
    addresses = []
    for entry in _as_dict_list(payload, SOURCE_IP):
        addresses.append(
            {
                "interface": str(entry.get("InterfaceAlias", "")),
                "ip_address": str(entry.get("IPAddress", "")),
                "prefix_length": entry.get("PrefixLength"),
                "address_family": str(entry.get("AddressFamily", "")),
                "prefix_origin": str(entry.get("PrefixOrigin", "")),
            }
        )
    return [address for address in addresses if address["ip_address"]][:limit]


def get_dns_config_live(timeout_s: float) -> list[dict]:
    payload = _run_powershell(_DNS_SCRIPT, SOURCE_DNS, timeout_s)
    configs = []
    for entry in _as_dict_list(payload, SOURCE_DNS):
        servers = entry.get("ServerAddresses", [])
        if not isinstance(servers, list):
            servers = [servers]
        configs.append(
            {
                "interface": str(entry.get("InterfaceAlias", "")),
                "servers": [str(server) for server in servers if str(server)],
            }
        )
    return [config for config in configs if config["interface"]]


def get_connections_live(timeout_s: float, limit: int) -> list[dict]:
    payload = _run_powershell(_CONNECTIONS_SCRIPT, SOURCE_CONNECTIONS, timeout_s)
    connections = []
    for entry in _as_dict_list(payload, SOURCE_CONNECTIONS):
        connections.append(
            {
                "local_address": str(entry.get("LocalAddress", "")),
                "local_port": entry.get("LocalPort"),
                "remote_address": str(entry.get("RemoteAddress", "")),
                "remote_port": entry.get("RemotePort"),
                "state": str(entry.get("State", "")),
                "owning_process_id": entry.get("OwningProcess"),
            }
        )
    return connections[:limit]


def validate_hostname(value: str) -> str:
    """Strict hostname validation for the single-query DNS test."""
    text = (value or "").strip().rstrip(".")
    if not text or len(text) > 253 or not _HOSTNAME_PATTERN.match(text):
        raise ValueError(
            f"Invalid hostname {value!r}: expected a dot-separated DNS name "
            "(letters, digits, hyphens)."
        )
    return text


def resolve_hostname_live(hostname: str, timeout_s: float) -> dict:
    """ACTIVE TEST: one A/AAAA lookup of a validated hostname (DnsOnly)."""
    clean = validate_hostname(hostname)
    script = _RESOLVE_SCRIPT_TEMPLATE.replace("{hostname}", clean)
    started = time.monotonic()
    try:
        payload = _run_powershell(script, SOURCE_RESOLVE, timeout_s)
        records = _as_dict_list(payload, SOURCE_RESOLVE)
    except DiagnosticCommandError as exc:
        return {
            "hostname": clean,
            "succeeded": False,
            "query_ms": int((time.monotonic() - started) * 1000),
            "addresses": [],
            "error": str(exc),
        }
    addresses = sorted(
        {
            str(record.get("IPAddress", ""))
            for record in records
            if str(record.get("IPAddress", ""))
        }
    )
    return {
        "hostname": clean,
        "succeeded": bool(addresses),
        "query_ms": int((time.monotonic() - started) * 1000),
        "addresses": addresses[:8],
        "error": None if addresses else "No A/AAAA records returned.",
    }
