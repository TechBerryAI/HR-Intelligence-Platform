"""Runtime registries."""

from runtime.registry.capability_registry import CapabilityRegistry
from runtime.registry.model_registry import ModelRegistry
from runtime.registry.prompt_registry import PromptRegistry
from runtime.registry.schema_registry import SchemaRegistry
from runtime.registry.task_registry import TaskRegistry

__all__ = [
    "CapabilityRegistry",
    "ModelRegistry",
    "PromptRegistry",
    "SchemaRegistry",
    "TaskRegistry",
]
