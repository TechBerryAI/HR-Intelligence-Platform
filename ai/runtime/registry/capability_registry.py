"""Capability registry — source of truth for AI capabilities."""

from __future__ import annotations

import sys
from pathlib import Path

from runtime.config.models import PromptRecord, SchemaRecord, TaskDefinition
from runtime.exceptions import RegistryError, TaskNotFoundError

_AI_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from capabilities.loader import CapabilityLoadError, discover_capabilities
from capabilities.models import CapabilityPackage


class CapabilityNotFoundError(TaskNotFoundError):
    """Requested capability is not registered."""


class CapabilityRegistry:
    """Loads and resolves self-contained capability packages."""

    def __init__(self, capabilities_dir: Path) -> None:
        self._capabilities_dir = capabilities_dir
        self._capabilities: dict[str, CapabilityPackage] = {}
        self.reload()

    @property
    def capabilities_dir(self) -> Path:
        return self._capabilities_dir

    def reload(self) -> None:
        if not self._capabilities_dir.exists():
            raise RegistryError(f"Capabilities directory not found: {self._capabilities_dir}")
        try:
            self._capabilities = discover_capabilities(self._capabilities_dir)
        except CapabilityLoadError as exc:
            raise RegistryError(str(exc)) from exc

    def get(self, capability_id: str) -> CapabilityPackage:
        package = self._capabilities.get(capability_id)
        if package is None:
            raise CapabilityNotFoundError(f"Capability not registered: {capability_id}")
        if package.status != "active":
            raise CapabilityNotFoundError(f"Capability is not active: {capability_id}")
        return package

    def has(self, capability_id: str) -> bool:
        return capability_id in self._capabilities

    def list_capabilities(self) -> list[CapabilityPackage]:
        return sorted(self._capabilities.values(), key=lambda item: item.id)

    def get_task(self, task_name: str) -> TaskDefinition:
        """Resolve a runtime task name to a TaskDefinition via capability."""
        package = self.get(task_name)
        return TaskDefinition(**package.to_task_definition())

    def list_tasks(self) -> list[TaskDefinition]:
        return [TaskDefinition(**package.to_task_definition()) for package in self.list_capabilities()]

    def get_prompt_record(self, prompt_id: str) -> PromptRecord:
        for package in self._capabilities.values():
            if package.prompt_id == prompt_id:
                return PromptRecord(
                    id=package.prompt_id,
                    version=package.metadata.version,
                    status=package.status,
                    template_file="prompt.md",
                    variables=["input", "context", "locale"],
                    description=package.metadata.description,
                )
        raise RegistryError(f"Prompt not registered: {prompt_id}")

    def resolve_prompt(self, prompt_id: str, *, variables: dict[str, str]) -> str:
        package = self._find_by_prompt_id(prompt_id)
        resolved = package.prompt_text
        for key, value in variables.items():
            resolved = resolved.replace(f"{{{{{key}}}}}", value)
        return resolved

    def get_schema_record(self, schema_id: str) -> SchemaRecord:
        for package in self._capabilities.values():
            if package.schema_id == schema_id:
                return SchemaRecord(
                    id=package.schema_id,
                    version=package.metadata.version,
                    status=package.status,
                    schema_file="schema.json",
                    format="json_schema",
                    description=package.metadata.description,
                )
        raise RegistryError(f"Schema not registered: {schema_id}")

    def resolve_schema(self, schema_id: str) -> dict | None:
        package = self._find_by_schema_id(schema_id)
        return package.schema_doc

    def list_prompts(self) -> list[PromptRecord]:
        seen: set[str] = set()
        records: list[PromptRecord] = []
        for package in self.list_capabilities():
            if package.prompt_id in seen:
                continue
            seen.add(package.prompt_id)
            records.append(self.get_prompt_record(package.prompt_id))
        return records

    def list_schemas(self) -> list[SchemaRecord]:
        seen: set[str] = set()
        records: list[SchemaRecord] = []
        for package in self.list_capabilities():
            if package.schema_id in seen:
                continue
            seen.add(package.schema_id)
            records.append(self.get_schema_record(package.schema_id))
        return records

    def _find_by_prompt_id(self, prompt_id: str) -> CapabilityPackage:
        for package in self._capabilities.values():
            if package.prompt_id == prompt_id:
                return package
        raise RegistryError(f"Prompt not registered: {prompt_id}")

    def _find_by_schema_id(self, schema_id: str) -> CapabilityPackage:
        for package in self._capabilities.values():
            if package.schema_id == schema_id:
                return package
        raise RegistryError(f"Schema not registered: {schema_id}")
