"""Allowlisted, read-only Windows OS and network diagnostics.

Additional read-only operations (extending windows_tools):

  4. Get-CimInstance Win32_OperatingSystem (basic OS information)
  5. Get-NetAdapter (adapter status)
  6. Get-NetIPAddress (IP configuration)
  7. Get-DnsClientServerAddress (DNS configuration)
  8. Get-NetTCPConnection -State Established (bounded connection sample)

Nothing here changes system state.
"""

from __future__ import annotations

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
