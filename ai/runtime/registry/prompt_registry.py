"""Prompt registry backed by the Capability Library."""

from __future__ import annotations

from pathlib import Path

from runtime.config.models import PromptRecord
from runtime.exceptions import RegistryError
from runtime.registry.capability_registry import CapabilityRegistry
from runtime.utils.env import load_yaml_with_env


class PromptRegistry:
    """Versioned prompt metadata registry."""

    def __init__(
        self,
        definitions_dir: Path | None = None,
        *,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self._definitions_dir = definitions_dir
        self._capabilities = capability_registry
        self._prompts: dict[str, PromptRecord] = {}
        self.reload()

    @property
    def definitions_dir(self) -> Path | None:
        return self._definitions_dir

    def reload(self) -> None:
        if self._capabilities is not None:
            self._prompts = {record.id: record for record in self._capabilities.list_prompts()}
            return

        self._prompts = {}
        if self._definitions_dir is None or not self._definitions_dir.exists():
            return

        for path in sorted(self._definitions_dir.glob("*.yaml")):
            raw = load_yaml_with_env(path)
            record = PromptRecord(**raw)
            self._prompts[record.id] = record

    def get(self, prompt_id: str) -> PromptRecord:
        record = self._prompts.get(prompt_id)
        if record is None:
            raise RegistryError(f"Prompt not registered: {prompt_id}")
        if record.status != "active":
            raise RegistryError(f"Prompt is not active: {prompt_id}")
        return record

    def resolve(self, prompt_id: str, *, variables: dict[str, str]) -> str:
        """Resolve prompt text from registry metadata and variables."""
        if self._capabilities is not None:
            return self._capabilities.resolve_prompt(prompt_id, variables=variables)

        record = self.get(prompt_id)
        template = self._load_template(record)
        resolved = template
        for key, value in variables.items():
            resolved = resolved.replace(f"{{{{{key}}}}}", value)
        return resolved

    def list_prompts(self) -> list[PromptRecord]:
        return sorted(self._prompts.values(), key=lambda item: item.id)

    def _load_template(self, record: PromptRecord) -> str:
        if record.template_file and self._definitions_dir is not None:
            template_path = self._definitions_dir / record.template_file
            if template_path.exists():
                return template_path.read_text(encoding="utf-8")
        return (
            f"[prompt:{record.id} v{record.version}] "
            "Process the following input and return structured output.\n\n"
            "{{input}}"
        )
