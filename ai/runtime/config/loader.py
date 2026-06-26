"""Configuration loading for AI runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from runtime.config.models import RuntimeConfig, RuntimeSettings, RoutingConfig
from runtime.exceptions import ConfigurationError
from runtime.utils.env import load_yaml_with_env

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = RUNTIME_ROOT / "config" / "runtime.default.yaml"


class RuntimeEnvSettings(BaseSettings):
    """Environment variable overrides for runtime."""

    model_config = SettingsConfigDict(
        env_prefix="AI_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    config_path: Path | None = None
    primary_provider: str | None = None
    default_timeout_seconds: float | None = None
    max_input_chars: int | None = None
    fail_on_validation_error: bool | None = None


def _resolve_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise ConfigurationError(f"Runtime configuration not found: {path}")
        return path

    env_settings = RuntimeEnvSettings()
    candidates = [
        env_settings.config_path,
        os.environ.get("AI_RUNTIME_CONFIG"),
        DEFAULT_CONFIG_PATH,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate).expanduser().resolve()
        if path.exists():
            return path
    raise ConfigurationError(
        "Runtime configuration not found. "
        f"Copy {DEFAULT_CONFIG_PATH.name} or set AI_RUNTIME_CONFIG."
    )


def _apply_env_overrides(config: RuntimeConfig, env_settings: RuntimeEnvSettings) -> RuntimeConfig:
    updates: dict[str, Any] = {}
    if env_settings.primary_provider:
        updates["routing"] = config.routing.model_copy(
            update={"primary": env_settings.primary_provider}
        )
    settings_updates: dict[str, Any] = {}
    if env_settings.default_timeout_seconds is not None:
        settings_updates["default_timeout_seconds"] = env_settings.default_timeout_seconds
    if env_settings.max_input_chars is not None:
        settings_updates["max_input_chars"] = env_settings.max_input_chars
    if settings_updates:
        updates["settings"] = config.settings.model_copy(update=settings_updates)
    if env_settings.fail_on_validation_error is not None:
        updates["validation"] = config.validation.model_copy(
            update={"fail_on_validation_error": env_settings.fail_on_validation_error}
        )
    if not updates:
        return config
    return config.model_copy(update=updates)


def load_runtime_config(config_path: Path | None = None) -> RuntimeConfig:
    """Load and validate runtime configuration from YAML and environment."""
    path = _resolve_config_path(config_path)
    raw = load_yaml_with_env(path)
    runtime_section = raw.get("runtime", raw)
    if not isinstance(runtime_section, dict):
        raise ConfigurationError(f"Invalid runtime config structure: {path}")

    base_dir = path.parent
    config = RuntimeConfig(
        settings=RuntimeSettings(**runtime_section.get("settings", {})),
        routing=RoutingConfig(**runtime_section["routing"]),
        providers=runtime_section.get("providers", {}),
        retry=runtime_section.get("retry", {}),
        validation=runtime_section.get("validation", {}),
        capabilities_dir=_resolve_relative(base_dir, runtime_section.get("capabilities_dir")),
        tasks_config_path=_resolve_relative(base_dir, runtime_section.get("tasks_config_path")),
        prompts_dir=_resolve_relative(base_dir, runtime_section.get("prompts_dir")),
        schemas_dir=_resolve_relative(base_dir, runtime_section.get("schemas_dir")),
        models_config_path=_resolve_relative(base_dir, runtime_section.get("models_config_path")),
    )
    return _apply_env_overrides(config, RuntimeEnvSettings())


def _resolve_relative(base_dir: Path, value: str | Path | None) -> Path | None:
    if value is None or value == "":
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path.expanduser().resolve()
