"""Allowlisted, read-only Windows Scheduled Tasks diagnostics.

  10. Get-ScheduledTask (definitions: triggers, actions, principals)
  11. Get-ScheduledTask | Get-ScheduledTaskInfo (last/next run, last result)

Windows PowerShell serializes CIM instances as Name/Value property lists plus
numeric enums and /Date()/ timestamps; this module normalizes those into
readable records. Outputs are minimized for privacy before they leave here:
action arguments are truncated, secret-like values are redacted, and the
current username is masked. Task definitions are read; nothing is created,
modified, disabled, deleted, or executed.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from .windows_tools import (
    DiagnosticCommandError,
    _as_dict_list,
    _run_powershell,
)

SOURCE_TASKS = "powershell:Get-ScheduledTask"
SOURCE_TASK_INFO = "powershell:Get-ScheduledTaskInfo"

MAX_ARGUMENT_CHARS = 300
MAX_DESCRIPTION_CHARS = 500

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd|secret|token|apikey|api_key|clientsecret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)--?(password|passwd|pwd|secret|token|apikey|api_key)\s+\S+"),
)

_TASKS_SCRIPT = (
    'Get-ScheduledTask | ForEach-Object { $t = $_; [PSCustomObject]@{ '
    'TaskName = $t.TaskName; TaskPath = $t.TaskPath; State = $t.State.ToString(); '
    'Author = $t.Author; Description = $t.Description; '
    'Principal = [PSCustomObject]@{ UserId = $t.Principal.UserId; '
    'LogonType = [int]$t.Principal.LogonType; RunLevel = [int]$t.Principal.RunLevel }; '
    'Triggers = @($t.Triggers | ForEach-Object { [PSCustomObject]@{ '
    'Type = $_.CimClass.CimClassName; Enabled = $_.Enabled; '
    'StartBoundary = $_.StartBoundary; EndBoundary = $_.EndBoundary; '
    'RepetitionInterval = "$($_.Repetition.Interval)"; '
    'RepetitionDuration = "$($_.Repetition.Duration)"; '
    'DaysInterval = $_.DaysInterval; WeeksInterval = $_.WeeksInterval } }); '
    'Actions = @($t.Actions | ForEach-Object { [PSCustomObject]@{ Execute = $_.Execute; '
    'Arguments = $_.Arguments; WorkingDirectory = $_.WorkingDirectory } }) } } '
    '| ConvertTo-Json -Compress -Depth 5'
)
_TASK_INFO_SCRIPT = (
    "Get-ScheduledTask | Get-ScheduledTaskInfo "
    "| Select-Object TaskName,TaskPath,LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns "
    "| ConvertTo-Json -Compress -Depth 3"
)

_FOLDER_RE = re.compile(r"\\[A-Za-z0-9_\\ .\-]*")
_NAME_CONTAINS_RE = re.compile(r"[A-Za-z0-9_ .\-]{0,64}")
_PS_DATE_RE = re.compile(r"/Date\((\d+)(?:[+-]\d{4})?\)/")

_TASK_STATE_NAMES = {0: "Unknown", 1: "Disabled", 2: "Queued", 3: "Ready", 4: "Running"}
_LOGON_TYPE_NAMES = {
    0: "None",
    1: "Password",
    2: "S4U",
    3: "Interactive",
    4: "Group",
    5: "ServiceAccount",
    6: "InteractiveOrPassword",
}
_RUN_LEVEL_NAMES = {0: "Limited", 1: "Highest"}

_TRIGGER_FIELDS = (
    "Enabled",
    "StartBoundary",
    "EndBoundary",
    "ExecutionTimeLimit",
    "DaysInterval",
    "WeeksInterval",
    "RandomDelay",
)


def sanitize_task_text(text: str, username: str | None) -> str:
    cleaned = text or ""
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(r"\1=[REDACTED]", cleaned)
    if username:
        cleaned = re.sub(re.escape(username), "<user>", cleaned, flags=re.IGNORECASE)
    return cleaned


def truncate_arguments(arguments: str) -> str:
    if len(arguments) <= MAX_ARGUMENT_CHARS:
        return arguments
    return arguments[:MAX_ARGUMENT_CHARS] + "…[truncated]"


def current_username() -> str | None:
    return os.environ.get("USERNAME") or os.environ.get("USER")


def _cim_properties(cim: dict) -> dict[str, Any]:
    """Flatten a serialized CIM instance's Name/Value property list."""
    props: dict[str, Any] = {}
    raw = cim.get("CimInstanceProperties", [])
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and "Name" in entry:
                props[str(entry["Name"])] = entry.get("Value")
    return props


def _task_state_name(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int) and value in _TASK_STATE_NAMES:
        return _TASK_STATE_NAMES[value]
    text = str(value or "").strip()
    if text.isdigit() and int(text) in _TASK_STATE_NAMES:
        return _TASK_STATE_NAMES[int(text)]
    return text or "Unknown"


def _ps_datetime(value: object) -> object:
    """Convert /Date(ms)/ stamps to ISO-8601 UTC; pass everything else through."""
    if not isinstance(value, str):
        return value
    match = _PS_DATE_RE.search(value)
    if not match:
        return value
    try:
        moment = datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return value
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _trigger_type(trigger: dict) -> str:
    for key in ("Type", "type"):
        if trigger.get(key):
            return str(trigger[key])
    direct = trigger.get("CimSystemProperties")
    if isinstance(direct, dict) and direct.get("ClassName"):
        return str(direct["ClassName"])
    cim = trigger.get("CimClass")
    props = cim.get("CimSystemProperties") if isinstance(cim, dict) else None
    classname = props.get("ClassName", "") if isinstance(props, dict) else ""
    return str(classname) if classname else "Unknown"


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _summarize_trigger(trigger: dict) -> dict[str, Any]:
    props = _cim_properties(trigger)
    summary: dict[str, Any] = {"type": _trigger_type(trigger)}
    for key in _TRIGGER_FIELDS:
        value = props.get(key, trigger.get(key))
        if value is None or value == "":
            continue
        if "boundary" in key.lower():
            summary[_snake_case(key)] = _ps_datetime(value)
        elif isinstance(value, (str, int, float, bool)):
            summary[_snake_case(key)] = value
        else:
            summary[_snake_case(key)] = str(value)[:200]
    interval = props.get(
        "RepetitionInterval",
        trigger.get("RepetitionInterval", trigger.get("repetition_interval")),
    )
    if interval:
        summary["repetition_interval"] = str(interval)
    else:
        repetition = props.get("Repetition", trigger.get("Repetition"))
        if isinstance(repetition, dict):
            nested = _cim_properties(repetition).get("Interval", repetition.get("Interval"))
            if nested:
                summary["repetition_interval"] = str(nested)
        elif repetition:
            summary["repetition"] = str(repetition)[:200]
    duration = props.get(
        "RepetitionDuration", trigger.get("RepetitionDuration", trigger.get("repetition_duration"))
    )
    if duration:
        summary["repetition_duration"] = str(duration)
    return summary


def _summarize_action(raw: dict, username: str | None) -> dict[str, str]:
    props = _cim_properties(raw)
    execute = props.get("Execute", raw.get("execute", raw.get("Execute", "")))
    arguments = props.get("Arguments", raw.get("arguments", raw.get("Arguments", "")))
    working = props.get(
        "WorkingDirectory", raw.get("working_directory", raw.get("WorkingDirectory", ""))
    )
    return {
        "execute": sanitize_task_text(str(execute or ""), username),
        "arguments": truncate_arguments(sanitize_task_text(str(arguments or ""), username)),
        "working_directory": sanitize_task_text(str(working or ""), username),
    }


def _enum_name(value: object, names: dict[int, str]) -> str:
    number: int | None = None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        number = value
    else:
        text = str(value or "").strip()
        if not text:
            return "Unknown"
        if text.isdigit():
            number = int(text)
        else:
            return text
    if number is not None and number in names:
        return f"{names[number]} ({number})"
    return str(number)


def _summarize_principal(raw: dict, username: str | None) -> dict[str, str]:
    props = _cim_properties(raw)
    user_id = props.get("UserId", raw.get("user_id", raw.get("UserId", "")))
    logon = props.get("LogonType", raw.get("logon_type", raw.get("LogonType", "")))
    level = props.get("RunLevel", raw.get("run_level", raw.get("RunLevel", "")))
    return {
        "user_id": sanitize_task_text(str(user_id or ""), username),
        "logon_type": _enum_name(logon, _LOGON_TYPE_NAMES),
        "run_level": _enum_name(level, _RUN_LEVEL_NAMES),
    }


def sanitize_task_record(task: dict[str, Any], username: str | None) -> dict[str, Any]:
    """Return a privacy-minimized copy of one summarized task record."""
    actions = []
    for action in task.get("actions", []):
        if not isinstance(action, dict):
            continue
        actions.append(
            {
                "execute": sanitize_task_text(str(action.get("execute", "")), username),
                "arguments": truncate_arguments(
                    sanitize_task_text(str(action.get("arguments", "")), username)
                ),
                "working_directory": sanitize_task_text(
                    str(action.get("working_directory", "")), username
                ),
            }
        )
    principal = task.get("principal", {})
    if not isinstance(principal, dict):
        principal = {}
    return {
        **task,
        "author": sanitize_task_text(str(task.get("author", "")), username),
        "description": sanitize_task_text(
            str(task.get("description", ""))[:MAX_DESCRIPTION_CHARS], username
        ),
        "principal": {
            "user_id": sanitize_task_text(str(principal.get("user_id", "")), username),
            "logon_type": str(principal.get("logon_type", "")),
            "run_level": str(principal.get("run_level", "")),
        },
        "actions": actions,
    }


def _as_list(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def get_scheduled_tasks_live(timeout_s: float) -> list[dict[str, Any]]:
    definitions = _as_dict_list(_run_powershell(_TASKS_SCRIPT, SOURCE_TASKS, timeout_s), SOURCE_TASKS)
    try:
        infos = _as_dict_list(
            _run_powershell(_TASK_INFO_SCRIPT, SOURCE_TASK_INFO, timeout_s), SOURCE_TASK_INFO
        )
    except (DiagnosticCommandError, ValueError):
        infos = []
    by_key = {(str(i.get("TaskPath", "")), str(i.get("TaskName", ""))): i for i in infos}
    username = current_username()
    tasks: list[dict[str, Any]] = []
    for entry in definitions:
        name = str(entry.get("TaskName", ""))
        path = str(entry.get("TaskPath", ""))
        if not name:
            continue
        info = by_key.get((path, name), {})
        last_result = info.get("LastTaskResult")
        raw = {
            "task_name": name,
            "task_path": path,
            "state": _task_state_name(entry.get("State", "")),
            "author": str(entry.get("Author", "")),
            "description": str(entry.get("Description", "")),
            "principal": _summarize_principal(entry.get("Principal") or {}, username),
            "triggers": [_summarize_trigger(t) for t in _as_list(entry.get("Triggers"))][:8],
            "actions": [_summarize_action(a, username) for a in _as_list(entry.get("Actions"))][:8],
            "last_run_time": _ps_datetime(str(info.get("LastRunTime", ""))),
            "last_task_result": last_result,
            "last_run_succeeded": (last_result == 0) if isinstance(last_result, int) else None,
            "next_run_time": _ps_datetime(str(info.get("NextRunTime", ""))),
            "missed_runs": info.get("NumberOfMissedRuns"),
        }
        tasks.append(sanitize_task_record(raw, username))
    return tasks


def validate_task_filters(folder: str, name_contains: str) -> tuple[str, str]:
    folder = (folder or "\\").strip() or "\\"
    if not _FOLDER_RE.fullmatch(folder):
        raise ValueError(f"Invalid task folder {folder!r}.")
    name_contains = (name_contains or "").strip()
    if not _NAME_CONTAINS_RE.fullmatch(name_contains):
        raise ValueError(f"Invalid name filter {name_contains!r}.")
    return folder, name_contains


def apply_task_filters(
    tasks: list[dict[str, Any]],
    folder: str,
    name_contains: str,
    include_microsoft: bool,
    limit: int,
    action_contains: str = "",
) -> tuple[list[dict[str, Any]], int]:
    folder, name_contains = validate_task_filters(folder, name_contains)
    action_contains = (action_contains or "").strip()
    if action_contains and not _NAME_CONTAINS_RE.fullmatch(action_contains):
        raise ValueError(f"Invalid action filter {action_contains!r}.")
    total = len(tasks)
    kept = []
    for task in tasks:
        if not str(task.get("task_path", "")).startswith(folder):
            continue
        if not include_microsoft and str(task.get("task_path", "")).lower().startswith("\\microsoft"):
            continue
        if name_contains and name_contains.lower() not in str(task.get("task_name", "")).lower():
            continue
        if action_contains:
            haystack = " ".join(
                f"{a.get('execute', '')} {a.get('arguments', '')}"
                for a in task.get("actions", [])
                if isinstance(a, dict)
            )
            if action_contains.lower() not in haystack.lower():
                continue
        kept.append(task)
    return kept[:limit], total
