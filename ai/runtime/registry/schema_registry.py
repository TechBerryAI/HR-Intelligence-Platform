"""Schema registry backed by the Capability Library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.config.models import SchemaRecord
from runtime.exceptions import RegistryError, SchemaNotFoundError
from runtime.registry.capability_registry import CapabilityRegistry
from runtime.utils.env import load_yaml_with_env


class SchemaRegistry:
    """Versioned schema metadata registry."""

    def __init__(
        self,
        definitions_dir: Path | None = None,
        *,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self._definitions_dir = definitions_dir
        self._capabilities = capability_registry
        self._schemas: dict[str, SchemaRecord] = {}
        self._cache: dict[str, dict[str, Any] | None] = {}
        self.reload()

    @property
    def definitions_dir(self) -> Path | None:
        return self._definitions_dir

    def reload(self) -> None:
        self._cache = {}
        if self._capabilities is not None:
            self._schemas = {record.id: record for record in self._capabilities.list_schemas()}
            return

        self._schemas = {}
        if self._definitions_dir is None or not self._definitions_dir.exists():
            return

        for path in sorted(self._definitions_dir.glob("*.yaml")):
            raw = load_yaml_with_env(path)
            record = SchemaRecord(**raw)
            self._schemas[record.id] = record

    def get(self, schema_id: str) -> SchemaRecord:
        record = self._schemas.get(schema_id)
        if record is None:
            raise SchemaNotFoundError(f"Schema not registered: {schema_id}")
        if record.status != "active":
            raise SchemaNotFoundError(f"Schema is not active: {schema_id}")
        return record

    def resolve(self, schema_id: str) -> dict[str, Any] | None:
        """Load JSON schema document when available."""
        if schema_id in self._cache:
            return self._cache[schema_id]

        if self._capabilities is not None:
            schema_doc = self._capabilities.resolve_schema(schema_id)
            self._cache[schema_id] = schema_doc
            return schema_doc

        record = self.get(schema_id)
        schema_doc: dict[str, Any] | None = None
        if record.schema_file and self._definitions_dir is not None:
            schema_path = self._definitions_dir / record.schema_file
            if schema_path.exists():
                schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
        self._cache[schema_id] = schema_doc
        return schema_doc

    def list_schemas(self) -> list[SchemaRecord]:
        return sorted(self._schemas.values(), key=lambda item: item.id)
