"""Pydantic models for forge.toolpack/v1 (BETA declares, lead wires).

Contracts law: docs/FORGE_CONTRACTS.md section 3 + D6 + D10.
Global rules: every new schema carries ``schema_version`` (reject unknown
major, warn on minor). Timeouts keep the global default; per-tool values
are advisory in v1 (D10). Never contract an unbuilt tool (D6).
"""

from __future__ import annotations

import re
import warnings
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = 1

ToolpackFamily = Literal["reliability", "networking", "devices", "applications", "office_local"]
ToolpackPrivileges = Literal["current_user_readonly", "elevated", "active_test"]
ToolSensitivity = Literal["public", "internal", "sensitive", "restricted"]
ToolImpactTier = Literal[
    "READ_ONLY",
    "MANUAL_INFORMATION",
    "SYSTEM_CHANGE",
    "PRIVILEGED_ACTION",
    "POTENTIALLY_DISRUPTIVE",
    "UNSUPPORTED_OR_UNSAFE",
]

_NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_CATEGORY_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_PACK_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
_IMPL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*\.[A-Za-z_][A-Za-z0-9_]*")
_MODEL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_VERSION_RE = re.compile(r"(\d+)\.(\d+)")


def _check_schema_version(value: str) -> str:
    text = (value or "").strip()
    match = _VERSION_RE.fullmatch(text)
    if not match:
        raise ValueError(f"Invalid schema_version {value!r}: expected 'major.minor'.")
    major, minor = int(match.group(1)), int(match.group(2))
    if major != SCHEMA_MAJOR:
        raise ValueError(f"Unsupported schema_version major {major}: expected {SCHEMA_MAJOR}.")
    if minor != 0:
        warnings.warn(f"Unknown schema_version minor {minor}; expected 0.", UserWarning, stacklevel=4)
    return text


class ToolDecl(BaseModel):
    """One tool declaration within a pack (forge.toolpack/v1 tools[] entry)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=64)
    args_model: str = Field(min_length=1, max_length=64)
    args_schema: dict[str, Any]
    impact_tier: ToolImpactTier
    timeout_s: float | None = None
    sensitivity: ToolSensitivity
    live_impl: str = Field(min_length=1)
    fixture_impl: str = Field(min_length=1)
    errors: list[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _NAME_RE.fullmatch(value):
            raise ValueError(
                f"Invalid tool name {value!r}: use 1-64 chars of a-z 0-9 _, starting with a letter."
            )
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Tool description must not be empty.")
        read_only = "(read-only" in text
        active = "ACTIVE TEST" in text
        if read_only == active:
            raise ValueError("Description must carry exactly one of '(read-only' or 'ACTIVE TEST'.")
        if active and "Changes nothing" not in text:
            raise ValueError("ACTIVE TEST descriptions must state 'Changes nothing'.")
        return value

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if not _CATEGORY_RE.fullmatch(value):
            raise ValueError(
                f"Invalid category {value!r}: use 1-64 chars of a-z 0-9 _, starting with a letter."
            )
        return value

    @field_validator("args_model")
    @classmethod
    def _validate_args_model(cls, value: str) -> str:
        if not _MODEL_RE.fullmatch(value):
            raise ValueError(f"Invalid args_model {value!r}: expected a pydantic model class name.")
        return value

    @field_validator("args_schema")
    @classmethod
    def _validate_args_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("args_schema must be a JSON-schema object.")
        if value.get("type") != "object":
            raise ValueError("args_schema must be an object schema with type 'object'.")
        return value

    @field_validator("timeout_s")
    @classmethod
    def _validate_timeout(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("timeout_s must be a number.")
        if not 0 < float(value) <= 300:
            raise ValueError("timeout_s must be within (0, 300].")
        return float(value)

    @field_validator("live_impl", "fixture_impl")
    @classmethod
    def _validate_impl(cls, value: str) -> str:
        text = value.strip()
        if not _IMPL_RE.fullmatch(text):
            raise ValueError(f"Invalid impl reference {value!r}: expected 'dotted.module.function'.")
        return text

    @field_validator("errors")
    @classmethod
    def _validate_errors(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for item in value:
            text = (item or "").strip()
            if not text:
                raise ValueError("errors[] entries must be non-empty strings.")
            if text in seen:
                raise ValueError(f"Duplicate errors[] entry {text!r}.")
            seen.add(text)
        return [(item or "").strip() for item in value]


class ToolPackSpec(BaseModel):
    """One modular toolpack declaration (forge.toolpack/v1)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    toolpack_id: str = Field(min_length=1, max_length=64)
    pack_version: str = Field(min_length=1, max_length=32)
    min_app_version: str = Field(min_length=1, max_length=32)
    privileges: ToolpackPrivileges
    family: ToolpackFamily
    tools: list[ToolDecl] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)

    @field_validator("toolpack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        if not _PACK_ID_RE.fullmatch(value):
            raise ValueError(
                f"Invalid toolpack_id {value!r}: use 1-64 chars of a-z 0-9 _ -, starting with a letter."
            )
        return value

    @field_validator("pack_version", "min_app_version")
    @classmethod
    def _validate_semver(cls, value: str) -> str:
        text = value.strip()
        if not _SEMVER_RE.fullmatch(text):
            raise ValueError(f"Invalid version {value!r}: expected semver 'x.y.z'.")
        return text

    @model_validator(mode="after")
    def _unique_tool_names(self) -> "ToolPackSpec":
        names = [tool.name for tool in self.tools]
        if len(set(names)) != len(names):
            dupes = sorted({name for name in names if names.count(name) > 1})
            raise ValueError(f"Duplicate tool names in pack: {', '.join(dupes)}.")
        return self


def check_global_uniqueness(packs: list[ToolPackSpec]) -> None:
    """Raise ValueError when two packs declare the same tool name.

    The lead registers every declared name into REGISTRY, so global
    uniqueness is required before wiring.
    """
    seen: dict[str, str] = {}
    for pack in packs:
        for tool in pack.tools:
            owner = seen.get(tool.name)
            if owner is not None:
                raise ValueError(
                    f"Tool {tool.name!r} declared by both {owner!r} and {pack.toolpack_id!r}."
                )
            seen[tool.name] = pack.toolpack_id
