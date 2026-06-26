"""Task registry backed by the Capability Library."""

from __future__ import annotations

from pathlib import Path

from runtime.config.models import TaskDefinition
from runtime.exceptions import RegistryError, TaskNotFoundError
from runtime.registry.capability_registry import CapabilityRegistry
from runtime.utils.env import load_yaml_with_env


class TaskRegistry:
    """Named capability registry for AI tasks."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self._config_path = config_path
        self._capabilities = capability_registry
        self._tasks: dict[str, TaskDefinition] = {}
        self.reload()

    @property
    def config_path(self) -> Path | None:
        return self._config_path

    def reload(self) -> None:
        if self._capabilities is not None:
            self._tasks = {task.name: task for task in self._capabilities.list_tasks()}
            return

        if self._config_path is None:
            raise RegistryError("Task registry requires capabilities_dir or tasks_config_path")
        if not self._config_path.exists():
            raise RegistryError(f"Task config not found: {self._config_path}")
        raw = load_yaml_with_env(self._config_path)
        tasks_section = raw.get("tasks", raw)
        if not isinstance(tasks_section, dict):
            raise RegistryError(f"Invalid tasks config: {self._config_path}")

        loaded: dict[str, TaskDefinition] = {}
        for name, payload in tasks_section.items():
            if not isinstance(payload, dict):
                raise RegistryError(f"Invalid task definition for {name}")
            loaded[name] = TaskDefinition(name=name, **payload)
        self._tasks = loaded

    def get(self, task_name: str) -> TaskDefinition:
        task = self._tasks.get(task_name)
        if task is None:
            raise TaskNotFoundError(f"Task not registered: {task_name}")
        return task

    def list_tasks(self) -> list[TaskDefinition]:
        return sorted(self._tasks.values(), key=lambda item: item.name)

    def has(self, task_name: str) -> bool:
        return task_name in self._tasks
