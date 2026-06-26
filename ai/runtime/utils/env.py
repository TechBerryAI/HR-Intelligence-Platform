"""Environment variable interpolation for YAML configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def interpolate_env(value: Any) -> Any:
    """Recursively resolve ``${VAR}`` and ``${VAR:default}`` placeholders."""
    if isinstance(value, str):
        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default = match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is not None and env_value != "":
                return env_value
            if default is not None:
                return default
            return ""

        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, list):
        return [interpolate_env(item) for item in value]
    if isinstance(value, dict):
        return {key: interpolate_env(item) for key, item in value.items()}
    return value


def load_yaml_with_env(path: Path) -> dict[str, Any]:
    """Load a YAML file and interpolate environment variables."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    resolved = interpolate_env(data)
    if not isinstance(resolved, dict):
        raise ValueError(f"Resolved YAML root must be a mapping: {path}")
    return resolved
