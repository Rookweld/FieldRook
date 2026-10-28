"""M017 local-model capability profiles.

A profile describes what a local model can do WITHOUT trusting the model
name alone: curated entries record verified facts (measured context,
observed vision support, benchmarked performance class), and anything
unknown resolves to the conservative default (text-only, small context).

Resolution order for each capability:
1. Explicit operator flags (FIELDROOK_LOCAL_MODEL_VISION / _TOOLS) — the
   operator asserts; a mismatch with the profile produces a warning, never
   silent enablement of a privacy-critical capability.
2. Curated profile entry matched by model name.
3. Conservative default: text only, 4096 context, unknown performance.

Vision is privacy-critical (screenshots leave FieldRook): it requires the
explicit flag AND a profile (or server report) that supports vision. The
FieldRook local path never uses chat tool-calling regardless of server
advertising — small models reason through the task pipeline instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocalModelProfile:
    """Inspectable capability record for one local model."""

    model: str
    context_window: int = 4096
    vision: bool = False
    # Server-advertised tool calling (informational: the local task path
    # does not use chat tools).
    server_tools: bool = False
    # Performance class from CPU benchmarks: fast / medium / slow /
    # workstation-only / unknown.
    perf_class: str = "unknown"
    storage_gb: float = 0.0
    params_b: float = 0.0
    thinking: bool = False
    notes: str = ""
    # Where the entry came from: curated (verified) or default (assumed).
    source: str = "curated"
    install_hint: str = ""
    # Token-budget multiplier for task calls. Models that always think
    # (thinking ignores the off switch) need room for thought + content.
    task_budget_scale: float = 1.0


# Curated from Ollama /api/show metadata + measurements on Fury
# (i7-13850HX, 68GB RAM, RTX 3500 Ada 12GB). M018 correction: all M017
# speed numbers were GPU-flavored (Ollama used the RTX silently); true
# CPU-only numbers are labeled CPU. Context lengths are server-reported.
CURATED_PROFILES: dict[str, LocalModelProfile] = {
    "qwen3:4b": LocalModelProfile(
        model="qwen3:4b",
        context_window=262144,
        vision=False,
        server_tools=True,
        perf_class="medium",
        storage_gb=2.5,
        params_b=4.0,
        thinking=True,
        notes="Default local text model. Thinking MUST be disabled via the Ollama "
        "think parameter (140s+ per call otherwise); /v1 ignores it. M018 "
        "challenge: 132/142 checks, quality 2.1/5 — revises hypotheses for "
        "real but fixates and rarely scopes. GPU triage ~2.5s; TRUE CPU "
        "triage ~25-33s at ~7 tok/s: too slow for the 10s laptop target.",
    ),
    "qwen3-vl:8b": LocalModelProfile(
        model="qwen3-vl:8b",
        context_window=262144,
        vision=True,
        server_tools=True,
        perf_class="slow",
        storage_gb=6.1,
        params_b=8.8,
        thinking=True,
        notes="Vision role: reads dialogs exactly (10.2s on GPU, exact code/title). "
        "Text tasks are unreliable even at 8x budget — thinking length varies and "
        "often exhausts the cap, and synth overclaims likelihood. Ignores the "
        "think-off switch. Configure for screenshot cases, not as the default.",
        task_budget_scale=8.0,
    ),
    "qwen3-coder:30b": LocalModelProfile(
        model="qwen3-coder:30b",
        context_window=262144,
        vision=False,
        server_tools=True,
        perf_class="workstation-only",
        storage_gb=18.6,
        params_b=30.5,
        thinking=False,
        notes="Workstation-only reference. Measured 19.2GB resident and ~26 tok/s "
        "(GPU-flavored) — valid structured text but far outside laptop "
        "budgets. Rejects multimodal input (HTTP 400), so it stays text-only.",
    ),
    "gemma4:e4b": LocalModelProfile(
        model="gemma4:e4b",
        context_window=131072,
        vision=True,
        server_tools=True,
        perf_class="balanced",
        storage_gb=9.6,
        params_b=8.0,
        thinking=True,
        notes="MoE: 9.6GB on disk but only ~3.2GB resident during tasks. M018 "
        "challenge leader: 135/142 checks, quality 3.45/5 — precise scoping "
        "questions, real revision, uses evidence readings. Costs ~2x wall "
        "time vs qwen3:4b. Caution: all-null vision on the readable dialog "
        "fixture (blind_vision) — screenshot reading unreliable despite the "
        "server advertising vision. True-CPU M019 (num_gpu=0, verified 100% CPU): "
        "triage 45-73s at ~4 tok/s — best local quality but not CPU-interactive.",
    ),
    "llama3.2:1b": LocalModelProfile(
        model="llama3.2:1b",
        context_window=131072,
        vision=False,
        server_tools=False,
        perf_class="fast",
        storage_gb=1.3,
        params_b=1.2,
        thinking=False,
        notes="Meta open-weight, measured M018: NOT RECOMMENDED. Quality 1.1/5 — "
        "echoes the problem as questions, invents readings, advised creating "
        "an admin account; 34/140 task calls unusable. Fast on CPU "
        "(triage ~8s) but unusable. Do not select for investigations.",
        install_hint="ollama pull llama3.2:1b  (~1.3GB)",
    ),
    "llama3.2:3b": LocalModelProfile(
        model="llama3.2:3b",
        context_window=131072,
        vision=False,
        server_tools=False,
        perf_class="fast",
        storage_gb=2.0,
        params_b=3.2,
        thinking=False,
        notes="Meta open-weight, measured M018: 132/142 checks, quality 2.5/5 — "
        "matches qwen3:4b structurally but leans on generic Event Viewer "
        "questions, repeats itself, and failed the disk-disproof behaviorally. "
        "CPU triage ~16-32s at ~9 tok/s. Viable alternative, not better.",
        install_hint="ollama pull llama3.2:3b  (~2.0GB)",
    ),
}


def resolve_profile(model_name: str) -> LocalModelProfile:
    """Curated profile by exact name, else the conservative default."""
    name = (model_name or "").strip()
    if name in CURATED_PROFILES:
        return CURATED_PROFILES[name]
    base = name.split(":")[0]
    for key, profile in CURATED_PROFILES.items():
        if key.split(":")[0] == base and base:
            return profile
    return LocalModelProfile(model=name or "unconfigured", source="default")


def describe_profile(profile: LocalModelProfile) -> dict:
    return {
        "model": profile.model,
        "context_window": profile.context_window,
        "vision": profile.vision,
        "server_tools": profile.server_tools,
        "perf_class": profile.perf_class,
        "storage_gb": profile.storage_gb,
        "params_b": profile.params_b,
        "thinking": profile.thinking,
        "notes": profile.notes,
        "source": profile.source,
        "install_hint": profile.install_hint,
    }


def effective_vision(flag_on: bool, profile: LocalModelProfile, server_caps: list[str]) -> bool:
    """Vision requires the explicit operator flag AND supporting evidence.

    Evidence is the curated profile or server-advertised capabilities —
    never the model name alone.
    """
    if not flag_on:
        return False
    advertised = {str(cap).strip().lower() for cap in server_caps or []}
    return bool(profile.vision or "vision" in advertised)


def vision_mismatch(
    flag_on: bool, profile: LocalModelProfile, server_caps: list[str] | None
) -> str | None:
    """Warn when the operator asserts vision nothing can support."""
    if flag_on and not effective_vision(flag_on, profile, server_caps or []):
        return (
            f"FIELDROOK_LOCAL_MODEL_VISION is set but neither the {profile.model} "
            f"profile ({profile.source}) nor the server supports vision; "
            "screenshots will be withheld until a vision-capable model is configured."
        )
    return None
