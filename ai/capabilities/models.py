"""Capability package data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CapabilityMetadata(BaseModel):
    """Metadata from capability.yaml."""

    model_config = {"populate_by_name": True}

    id: str
    name: str
    version: str
    owner: str = "ai-platform"
    status: str = "active"
    supported_providers: list[str] = Field(default_factory=list)
    supported_models: list[str] = Field(default_factory=list)
    input_type: str = "text"
    output_type: str = "json"
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    schema_ref: dict[str, str] = Field(default_factory=dict, alias="schema")
    prompt: dict[str, str] = Field(default_factory=dict)
    validation: dict[str, str] = Field(default_factory=dict)
    examples: dict[str, str] = Field(default_factory=dict)
    benchmarks: dict[str, str] = Field(default_factory=dict)


class CapabilityRuntimeConfig(BaseModel):
    """Execution parameters from runtime.yaml."""

    preferred_provider: str | None = None
    preferred_model_alias: str
    temperature: float = 0.2
    top_p: float = 1.0
    max_tokens: int = 2048
    streaming: bool = False
    timeout_seconds: float | None = None
    retries: int | None = None
    fallback_policy: str = "routing_chain"
    output_mode: str = "json"


class CapabilityPackage(BaseModel):
    """Fully loaded, self-contained AI capability."""

    metadata: CapabilityMetadata
    root_dir: Path
    prompt_text: str
    schema_doc: dict[str, Any]
    validation_rules: dict[str, Any]
    runtime_config: CapabilityRuntimeConfig

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def prompt_id(self) -> str:
        return self.metadata.prompt.get("id", self.id)

    @property
    def schema_id(self) -> str:
        return self.metadata.schema_ref.get("id", self.id)

    @property
    def status(self) -> str:
        return self.metadata.status

    def to_task_definition(self) -> dict[str, Any]:
        """Build task definition fields for runtime TaskRegistry."""
        rules = dict(self.validation_rules)
        return {
            "name": self.id,
            "prompt_id": self.prompt_id,
            "schema_id": self.schema_id,
            "model_alias": self.runtime_config.preferred_model_alias,
            "preferred_provider": self.runtime_config.preferred_provider,
            "temperature": self.runtime_config.temperature,
            "max_tokens": self.runtime_config.max_tokens,
            "validation": rules,
            "description": self.metadata.description,
        }
