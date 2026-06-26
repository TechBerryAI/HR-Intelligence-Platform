"""Capability registry and integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.config.loader import DEFAULT_CONFIG_PATH, load_runtime_config
from runtime.core.runtime import AIRuntime
from runtime.exceptions import RegistryError, SchemaNotFoundError, TaskNotFoundError
from runtime.registry.capability_registry import CapabilityRegistry
from runtime.registry.model_registry import ModelRegistry
from runtime.registry.prompt_registry import PromptRegistry
from runtime.registry.schema_registry import SchemaRegistry
from runtime.registry.task_registry import TaskRegistry


CAPABILITIES_DIR = Path(__file__).resolve().parents[2] / "capabilities"


def test_capability_registry_discovers_all_tasks() -> None:
    registry = CapabilityRegistry(CAPABILITIES_DIR)
    names = {cap.id for cap in registry.list_capabilities()}
    assert names == {
        "resume_parsing",
        "jd_parsing",
        "bulk_resume_parsing",
        "candidate_matching",
        "resume_summary",
        "interview_generation",
        "hr_chat",
    }


def test_capability_registry_resolves_prompt() -> None:
    registry = CapabilityRegistry(CAPABILITIES_DIR)
    text = registry.resolve_prompt("resume_parser_v1", variables={"input": "Jane Doe"})
    assert "Jane Doe" in text
    assert "resume_parser_v1" in text


def test_capability_registry_resolves_schema() -> None:
    registry = CapabilityRegistry(CAPABILITIES_DIR)
    schema = registry.resolve_schema("resume_v1")
    assert schema is not None
    assert schema["$id"] == "resume_v1"


def test_task_registry_lists_known_tasks() -> None:
    capabilities = CapabilityRegistry(CAPABILITIES_DIR)
    registry = TaskRegistry(capability_registry=capabilities)
    names = {task.name for task in registry.list_tasks()}
    assert "resume_parsing" in names
    assert "jd_parsing" in names
    assert "hr_chat" in names


def test_task_registry_missing_task() -> None:
    capabilities = CapabilityRegistry(CAPABILITIES_DIR)
    registry = TaskRegistry(capability_registry=capabilities)
    with pytest.raises(TaskNotFoundError):
        registry.get("not_a_task")


def test_prompt_registry_resolve_capability_template() -> None:
    capabilities = CapabilityRegistry(CAPABILITIES_DIR)
    registry = PromptRegistry(capability_registry=capabilities)
    text = registry.resolve("resume_parser_v1", variables={"input": "Jane Doe"})
    assert "Jane Doe" in text
    assert "Resume Parsing" in text


def test_schema_registry_resolves_json_schema() -> None:
    capabilities = CapabilityRegistry(CAPABILITIES_DIR)
    registry = SchemaRegistry(capability_registry=capabilities)
    record = registry.get("resume_v1")
    assert record.id == "resume_v1"
    schema = registry.resolve("resume_v1")
    assert schema is not None
    assert schema["$id"] == "resume_v1"


def test_schema_registry_missing() -> None:
    capabilities = CapabilityRegistry(CAPABILITIES_DIR)
    registry = SchemaRegistry(capability_registry=capabilities)
    with pytest.raises(SchemaNotFoundError):
        registry.get("missing_schema")


def test_model_registry_resolve_alias() -> None:
    models_path = Path(__file__).resolve().parents[1] / "config" / "models.default.yaml"
    registry = ModelRegistry(models_path)
    model = registry.resolve("resume-parser", provider_id="ollama")
    assert model == "qwen2.5:7b-instruct"


def test_model_registry_missing_alias() -> None:
    models_path = Path(__file__).resolve().parents[1] / "config" / "models.default.yaml"
    registry = ModelRegistry(models_path)
    with pytest.raises(RegistryError):
        registry.resolve("unknown-alias", provider_id="mock")


def test_runtime_loads_capabilities() -> None:
    runtime = AIRuntime.from_config_path(DEFAULT_CONFIG_PATH)
    assert runtime.capabilities is not None
    assert runtime.capabilities.has("resume_parsing")
