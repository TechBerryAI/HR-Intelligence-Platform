"""Runtime configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1)
    backoff_seconds: float = Field(default=2.0, ge=0.0)
    retry_on_status: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])


class RoutingConfig(BaseModel):
    primary: str
    fallback_chain: list[str] = Field(default_factory=list)


class ValidationConfig(BaseModel):
    fail_on_validation_error: bool = True


class RuntimeSettings(BaseModel):
    default_timeout_seconds: float = Field(default=45.0, ge=1.0)
    max_input_chars: int = Field(default=0, ge=0)


class RuntimeConfig(BaseModel):
    """Top-level runtime configuration."""

    settings: RuntimeSettings = Field(default_factory=RuntimeSettings)
    routing: RoutingConfig
    providers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    capabilities_dir: Path | None = None
    tasks_config_path: Path | None = None
    prompts_dir: Path | None = None
    schemas_dir: Path | None = None
    models_config_path: Path | None = None

    @field_validator(
        "capabilities_dir",
        "tasks_config_path",
        "prompts_dir",
        "schemas_dir",
        "models_config_path",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value: Any) -> Path | None:
        if value is None or value == "":
            return None
        return Path(value).expanduser().resolve()


class TaskDefinition(BaseModel):
    """Registered AI task capability."""

    name: str
    prompt_id: str
    schema_id: str
    model_alias: str
    preferred_provider: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048
    validation: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class PromptRecord(BaseModel):
    """Prompt registry metadata (template content loaded separately)."""

    id: str
    version: str
    status: str = "active"
    template_file: str | None = None
    variables: list[str] = Field(default_factory=list)
    description: str = ""


class SchemaRecord(BaseModel):
    """Schema registry metadata."""

    id: str
    version: str
    status: str = "active"
    schema_file: str | None = None
    format: str = "json_schema"
    description: str = ""


class ModelAliasRecord(BaseModel):
    """Model alias resolution entry."""

    alias: str
    default_provider: str | None = None
    models: dict[str, str] = Field(default_factory=dict)
    description: str = ""
