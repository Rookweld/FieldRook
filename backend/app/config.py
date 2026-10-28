"""FieldRook configuration.

All settings come from environment variables (optionally via a root `.env`
file). Secrets are never hardcoded and never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL_NAME = "muse-spark-1.3"
SIMULATED_MODEL_NAME = "fieldrook-simulated-001"


def _load_dotenv_file(path: Path) -> None:
    """Minimal `.env` loader (KEY=VALUE, `#` comments). Never overrides real env vars."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def offline_requested() -> bool:
    """Fail closed for explicit offline/test mode, regardless of .env credentials."""
    value = os.environ.get("FIELDROOK_OFFLINE", "").strip().lower()
    return value not in ("", "0", "false", "no", "off")


def _as_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _as_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    model_api_key: str | None
    model_base_url: str
    model_name: str
    fixtures_mode: str  # "auto" | "always" | "never"
    command_timeout_s: float
    model_timeout_s: float
    evidence_ttl_s: float = 900.0
    offline_mode: bool = False
    # M016: explicit inference-provider selection. "auto" keeps the legacy
    # behavior (Meta cloud when a key is set, else simulated).
    model_provider: str = "auto"  # "auto" | "meta" | "simulated" | "local"
    local_model_url: str = ""  # e.g. http://127.0.0.1:11434/v1 (loopback only)
    local_model_name: str = ""
    local_model_vision: bool = False
    local_model_tools: bool = False
    # M017: local API style + thinking control. auto probes for Ollama.
    local_api: str = "auto"  # "auto" | "openai" | "ollama"
    local_think: str = "auto"  # "auto" | "on" | "off" (auto disables thinking for task calls)


def load_settings() -> Settings:
    offline_mode = offline_requested()
    # In offline mode never even consult the operator's root .env.
    if not offline_mode:
        project_root = Path(__file__).resolve().parents[2]
        _load_dotenv_file(project_root / ".env")
    fixtures_mode = os.environ.get("FIELDROOK_FIXTURES", "auto").strip().lower()
    if fixtures_mode not in ("auto", "always", "never"):
        fixtures_mode = "auto"
    raw_key = "" if offline_mode else os.environ.get("MODEL_API_KEY", "").strip()
    provider = os.environ.get("FIELDROOK_MODEL_PROVIDER", "auto").strip().lower()
    if provider not in ("auto", "meta", "simulated", "local"):
        provider = "auto"
    local_api = os.environ.get("FIELDROOK_LOCAL_API", "auto").strip().lower()
    if local_api not in ("auto", "openai", "ollama"):
        local_api = "auto"
    local_think = os.environ.get("FIELDROOK_LOCAL_THINK", "auto").strip().lower()
    if local_think not in ("auto", "on", "off"):
        local_think = "auto"
    return Settings(
        model_api_key=raw_key or None,
        model_base_url=os.environ.get("MODEL_BASE_URL", DEFAULT_MODEL_BASE_URL).strip()
        or DEFAULT_MODEL_BASE_URL,
        model_name=os.environ.get("MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME,
        fixtures_mode=fixtures_mode,
        command_timeout_s=_as_float("FIELDROOK_CMD_TIMEOUT_S", 30.0),
        model_timeout_s=_as_float("FIELDROOK_MODEL_TIMEOUT_S", 60.0),
        evidence_ttl_s=_as_float("FIELDROOK_EVIDENCE_TTL_S", 900.0),
        offline_mode=offline_mode,
        model_provider=provider,
        local_model_url=os.environ.get("FIELDROOK_LOCAL_MODEL_URL", "").strip(),
        local_model_name=os.environ.get("FIELDROOK_LOCAL_MODEL_NAME", "").strip(),
        local_model_vision=_as_flag("FIELDROOK_LOCAL_MODEL_VISION"),
        local_model_tools=_as_flag("FIELDROOK_LOCAL_MODEL_TOOLS"),
        local_api=local_api,
        local_think=local_think,
    )
