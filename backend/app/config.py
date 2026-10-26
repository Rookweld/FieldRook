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


def _as_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    model_api_key: str | None
    model_base_url: str
    model_name: str
    fixtures_mode: str  # "auto" | "always" | "never"
    command_timeout_s: float
    model_timeout_s: float


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    _load_dotenv_file(project_root / ".env")
    fixtures_mode = os.environ.get("FIELDROOK_FIXTURES", "auto").strip().lower()
    if fixtures_mode not in ("auto", "always", "never"):
        fixtures_mode = "auto"
    raw_key = os.environ.get("MODEL_API_KEY", "").strip()
    return Settings(
        model_api_key=raw_key or None,
        model_base_url=os.environ.get("MODEL_BASE_URL", DEFAULT_MODEL_BASE_URL).strip()
        or DEFAULT_MODEL_BASE_URL,
        model_name=os.environ.get("MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME,
        fixtures_mode=fixtures_mode,
        command_timeout_s=_as_float("FIELDROOK_CMD_TIMEOUT_S", 30.0),
        model_timeout_s=_as_float("FIELDROOK_MODEL_TIMEOUT_S", 60.0),
    )
