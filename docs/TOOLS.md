# FieldRook Diagnostic Tool Reference

14 tools, generated from `backend/app/tools/registry.py` (descriptions below
mirror the registry; the registry is authoritative). The model requests tools
by name with schema-validated arguments; it can never send executable
commands.

Enforcement on every call: strict argument schemas, target allowlists, 8 + 4
call budget (12 total per investigation), per-tool timeouts, result
truncation, same-round duplicate suppression, graceful error outputs, and a
visible activity record. Every output carries `source` provenance
(`live:` / `fixture:`) and every result becomes evidence with a stable ID.

## Services & processes

### list_services

List Windows services with their current status (read-only).

- Category: `service_list` · Arguments: `limit: int`

### get_service_details

Read one service's status, startup configuration, and related System event
entries (read-only).

- Category: `service_details` · Arguments: `name: str`

### get_process_info

Read one process by name, pid, or hosting service name (exactly one
selector): executable path, start time, uptime, memory, and services hosted
in it (read-only). Full command lines are never collected.

- Category: `process_info` · Arguments: `name: str, pid: int, service_name: str`
- Notes: `ExecutablePath` reads return empty without elevation (graceful).
  Name lookups over many matches (e.g. `svchost.exe`) can take ~15s.

## Event logs & crashes

### search_event_logs

Search System and/or Application event logs for keyword matches in recent
error/warning entries (read-only, bounded).

- Category: `event_log` · Arguments: `keywords: str, logs: list, hours: int, max_events: int`

### search_application_crashes

Search the Application log for crash/hang evidence: Application Error
(1000), Error Reporting (1001), Application Hang (1002), .NET Runtime
(1026), with faulting app/module, exception codes, and timestamps
(read-only, bounded). Never reads dumps or user files.

- Category: `app_crashes` · Arguments: `app_name: str, hours: int, max_events: int`

## Network

### get_network_adapters

Read network adapter status, link speed, and MAC addresses (read-only).

- Category: `net_adapters` · Arguments: `limit: int`

### get_ip_config

Read configured IP addresses per interface (read-only).

- Category: `ip_config` · Arguments: `limit: int`

### get_dns_config

Read configured DNS servers per interface (read-only).

- Category: `dns_config` · Arguments: `(none)`

### get_connections

Sample currently established TCP connections: local and remote addresses
and ports (read-only, bounded).

- Category: `connections` · Arguments: `limit: int`

### test_dns_resolution

ACTIVE TEST: send one A/AAAA DNS query for a validated hostname and report
addresses and query time. Changes nothing; labeled as an active test in
provenance.

- Category: `dns_test` · Arguments: `hostname: str`
- Notes: the only non-passive tool. Hostnames are strictly validated; the
  triage planner runs at most one control query per DNS investigation.

## System, tasks, worker, error codes

### get_os_info

Read basic operating system information: edition, version, build, last boot
time (read-only).

- Category: `os_info` · Arguments: `(none)`

### get_scheduled_tasks

List Windows Scheduled Tasks with triggers, actions, principals, and
last-run results (read-only). Filters: folder prefix, task-name substring,
action substring (executable/arguments, e.g. powershell.exe),
Microsoft-task exclusion. Arguments are truncated and secret-like values
redacted.

- Category: `scheduled_tasks` · Arguments: `folder: str, name_contains: str, action_contains: str, include_microsoft: bool, limit: int`

### get_demo_worker_health

Read the application-owned FieldRook demo worker health: status, heartbeat
freshness, and verified process state (read-only).

- Category: `demo_worker` · Arguments: `(none)`

### interpret_error_code

Deterministically decode a Windows error code (decimal, hex, or signed
32-bit) into hex, family, and symbolic name when known (read-only
computation). Never guesses unknown codes.

- Category: `error_code` · Arguments: `value: str`
