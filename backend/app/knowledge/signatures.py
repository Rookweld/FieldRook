"""Deterministic incident fingerprints: category, symptoms, identity, codes.

Everything here is inspectable: normalized symptom tokens, a keyword-based
category, service/app identity, Windows event codes, and a small redacted
per-category evidence signature. No embeddings, no hidden scores.
"""

from __future__ import annotations

import re
from typing import Any

from ..analysis.loop import (
    CRASH_KEYWORDS,
    DNS_KEYWORDS,
    NETWORK_KEYWORDS,
    PERFORMANCE_KEYWORDS,
    SCHEDULED_KEYWORDS,
)
from .redact import redact_text, redact_value

STOPWORDS = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those", "is",
        "are", "was", "were", "be", "been", "being", "it", "its", "of", "on",
        "in", "to", "for", "with", "and", "or", "but", "not", "no", "do",
        "does", "did", "have", "has", "had", "can", "could", "would", "should",
        "will", "please", "help", "me", "i", "am", "so", "very", "just",
        "when", "what", "which", "who", "how", "there", "here", "from",
    }
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*")


def normalize_symptoms(problem: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(redact_text(problem or "").lower())
    kept = sorted({t for t in tokens if len(t) >= 3 and t not in STOPWORDS})
    return kept[:40]


def classify_category(problem: str, evidence: list[Any]) -> str:
    lowered = (problem or "").lower()
    if "demo worker" in lowered:
        return "demo-worker"
    categories = {getattr(item, "category", "") for item in evidence}
    if any(k in lowered for k in CRASH_KEYWORDS) or "app_crashes" in categories:
        return "applications"
    if any(k in lowered for k in DNS_KEYWORDS):
        return "network-dns"
    if any(k in lowered for k in NETWORK_KEYWORDS) or categories & {
        "net_adapters", "ip_config", "dns_config", "connections",
    }:
        return "network"
    if any(k in lowered for k in SCHEDULED_KEYWORDS) or "scheduled_tasks" in categories:
        return "scheduled-tasks"
    if any(k in lowered for k in PERFORMANCE_KEYWORDS):
        return "performance"
    if "service_details" in categories or "service_list" in categories:
        return "services"
    return "general"


def extract_identity(problem: str, service_name: str | None, evidence: list[Any]) -> str | None:
    if service_name:
        return f"service:{service_name.strip().lower()}"
    for item in evidence:
        if getattr(item, "category", "") == "service_details" and not getattr(item, "error", None):
            name = item.data.get("name")
            if name:
                return f"service:{str(name).strip().lower()}"
    apps: list[str] = []
    for item in evidence:
        if getattr(item, "category", "") == "app_crashes" and not getattr(item, "error", None):
            crashes = item.data.get("crashes", [])
            if isinstance(crashes, list):
                for crash in crashes:
                    if isinstance(crash, dict) and crash.get("app_name"):
                        apps.append(str(crash["app_name"]).strip().lower())
    if apps:
        return f"app:{apps[0]}"
    exe = re.findall(r"[a-z0-9_][a-z0-9_.-]*\.exe", (problem or "").lower())
    if exe:
        return f"app:{sorted(set(exe))[0]}"
    return None


def extract_event_codes(evidence: list[Any]) -> list[str]:
    codes: set[str] = set()
    for item in evidence:
        if getattr(item, "error", None):
            continue
        category = getattr(item, "category", "")
        data = getattr(item, "data", {}) or {}
        if category == "event_log":
            logs = data.get("logs", [])
            if isinstance(logs, list):
                for log in logs:
                    events = log.get("events", []) if isinstance(log, dict) else []
                    for event in events if isinstance(events, list) else []:
                        code = event.get("id") if isinstance(event, dict) else None
                        if isinstance(code, int):
                            codes.add(str(code))
        elif category == "app_crashes":
            crashes = data.get("crashes", [])
            if isinstance(crashes, list):
                for crash in crashes:
                    code = crash.get("id") if isinstance(crash, dict) else None
                    if isinstance(code, int):
                        codes.add(str(code))
    return sorted(codes)[:20]


def _service_hint(item: Any) -> str:
    data = getattr(item, "data", {}) or {}
    status = data.get("status", {})
    state = status.get("status", "?") if isinstance(status, dict) else "?"
    startup = data.get("startup", {})
    start = startup.get("startup_type", "?") if isinstance(startup, dict) else "?"
    return f"{redact_value(data.get('name'))}:{redact_value(state)}/{redact_value(start)}"


def _crash_hint(item: Any) -> str:
    data = getattr(item, "data", {}) or {}
    crashes = data.get("crashes", [])
    if not isinstance(crashes, list) or not crashes:
        return "no matches"
    first = crashes[0] if isinstance(crashes[0], dict) else {}
    return (
        f"{redact_value(first.get('app_name'))}#{redact_value(first.get('id'))}"
        f":{redact_value(first.get('exception_code'))}"
    )


def _adapters_hint(item: Any) -> str:
    data = getattr(item, "data", {}) or {}
    adapters = data.get("adapters", [])
    if not isinstance(adapters, list):
        return "?"
    states = sorted(
        f"{a.get('name', '?')}={a.get('status', '?')}"
        for a in adapters[:6]
        if isinstance(a, dict)
    )
    return redact_value(",".join(states))


def _tasks_hint(item: Any) -> str:
    data = getattr(item, "data", {}) or {}
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return "?"
    names = sorted(
        f"{t.get('task_name', '?')}:{t.get('last_task_result', '?')}"
        for t in tasks[:8]
        if isinstance(t, dict)
    )
    return redact_value(",".join(names))


def build_signature(evidence: list[Any]) -> dict[str, str]:
    """Small redacted salient values per category. Latest item wins."""
    signature: dict[str, str] = {}
    for item in evidence:
        if getattr(item, "error", None):
            continue
        category = getattr(item, "category", "")
        data = getattr(item, "data", {}) or {}
        if category == "service_details":
            signature[category] = _service_hint(item)
        elif category == "app_crashes":
            signature[category] = _crash_hint(item)
        elif category == "net_adapters":
            signature[category] = _adapters_hint(item)
        elif category == "scheduled_tasks":
            signature[category] = _tasks_hint(item)
        elif category == "demo_worker":
            signature[category] = (
                f"{redact_value(data.get('status'))}"
                f"/hb{redact_value(data.get('heartbeat_age_s'))}"
            )
        elif category == "dns_test":
            signature[category] = (
                f"{redact_value(data.get('hostname'))}:"
                f"{'ok' if data.get('succeeded') else 'fail'}"
            )
        elif category == "error_code":
            signature[category] = (
                f"{redact_value(data.get('hex'))}={redact_value(data.get('name'))}"
            )
        elif category == "os_info":
            signature[category] = f"build {redact_value(data.get('build_number'))}"
        elif category == "process_info":
            procs = data.get("processes", [])
            first = procs[0].get("name", "?") if isinstance(procs, list) and procs else "none"
            signature[category] = (
                f"{redact_value(first)}:{'found' if data.get('found') else 'absent'}"
            )
        elif category == "event_log":
            codes = sorted(
                {
                    str(e.get("id"))
                    for log in (data.get("logs", []) or [])
                    if isinstance(log, dict)
                    for e in (log.get("events", []) or [])
                    if isinstance(e, dict) and isinstance(e.get("id"), int)
                }
            )
            signature[category] = f"ids {','.join(codes[:8]) or 'none'}"
        elif category in ("service_list", "ip_config", "dns_config", "connections"):
            signature[category] = f"count {redact_value(data.get('count'))}"
    return signature


def cluster_key(category: str, symptoms: list[str], identity: str | None, codes: list[str]) -> str:
    import hashlib

    material = "|".join(
        [category, ",".join(sorted(symptoms)), identity or "", ",".join(sorted(codes))]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
