"""Model alias registry."""

from __future__ import annotations

from pathlib import Path

from runtime.config.models import ModelAliasRecord
from runtime.exceptions import RegistryError
from runtime.utils.env import load_yaml_with_env


class ModelRegistry:
    """Resolve logical model aliases to provider-specific model names."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._aliases: dict[str, ModelAliasRecord] = {}
        self.reload()

    @property
    def config_path(self) -> Path:
        return self._config_path

    def reload(self) -> None:
        if not self._config_path.exists():
            raise RegistryError(f"Model config not found: {self._config_path}")
        raw = load_yaml_with_env(self._config_path)
        aliases_section = raw.get("aliases", raw)
        if not isinstance(aliases_section, dict):
            raise RegistryError(f"Invalid models config: {self._config_path}")

        loaded: dict[str, ModelAliasRecord] = {}
        for alias, payload in aliases_section.items():
            if not isinstance(payload, dict):
                raise RegistryError(f"Invalid model alias definition: {alias}")
            loaded[alias] = ModelAliasRecord(alias=alias, **payload)
        self._aliases = loaded

    def get(self, alias: str) -> ModelAliasRecord:
        record = self._aliases.get(alias)
        if record is None:
            raise RegistryError(f"Model alias not registered: {alias}")
        return record

    def resolve(self, alias: str, *, provider_id: str) -> str:
        record = self.get(alias)
        if provider_id in record.models:
            return record.models[provider_id]
        if record.default_provider and record.default_provider in record.models:
            return record.models[record.default_provider]
        if record.models:
            return next(iter(record.models.values()))
        raise RegistryError(
            f"No model mapping for alias '{alias}' and provider '{provider_id}'"
        )

    def list_aliases(self) -> list[ModelAliasRecord]:
        return sorted(self._aliases.values(), key=lambda item: item.alias)
