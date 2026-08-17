"""AI Runtime public API."""



from __future__ import annotations



from collections import OrderedDict

from pathlib import Path

from threading import RLock

from typing import Any



from runtime.config.loader import load_runtime_config

from runtime.config.models import RuntimeConfig

from runtime.core.executor import TaskExecutor

from runtime.health.monitor import HealthMonitor

from runtime.metrics.collector import MetricsCollector

from providers.manager import ProviderManager

from runtime.registry.capability_registry import CapabilityRegistry

from runtime.registry.model_registry import ModelRegistry

from runtime.registry.prompt_registry import PromptRegistry

from runtime.registry.schema_registry import SchemaRegistry

from runtime.registry.task_registry import TaskRegistry





class AIRuntime:

    """Central orchestration layer for all AI capabilities."""



    def __init__(self, config: RuntimeConfig) -> None:

        self._config = config

        self._health = HealthMonitor()

        self._metrics = MetricsCollector()



        capabilities_dir = config.capabilities_dir

        tasks_path = config.tasks_config_path

        prompts_dir = config.prompts_dir

        schemas_dir = config.schemas_dir

        models_path = config.models_config_path



        if capabilities_dir is not None:

            self._capabilities = CapabilityRegistry(capabilities_dir)

            self._tasks = TaskRegistry(capability_registry=self._capabilities)

            self._prompts = PromptRegistry(capability_registry=self._capabilities)

            self._schemas = SchemaRegistry(capability_registry=self._capabilities)

        else:

            self._capabilities = None

            if tasks_path is None or prompts_dir is None or schemas_dir is None or models_path is None:

                raise ValueError(

                    "Runtime config must define capabilities_dir or legacy tasks, prompts, schemas, and models paths"

                )

            self._tasks = TaskRegistry(tasks_path)

            self._prompts = PromptRegistry(prompts_dir)

            self._schemas = SchemaRegistry(schemas_dir)



        if models_path is None:

            raise ValueError("Runtime config must define models_config_path")

        self._models = ModelRegistry(models_path)

        self._providers = ProviderManager(config, self._health)

        self._executor = TaskExecutor(

            config=config,

            provider_manager=self._providers,

            prompt_registry=self._prompts,

            schema_registry=self._schemas,

            model_registry=self._models,

            health_monitor=self._health,

            metrics=self._metrics,

            capability_registry=self._capabilities,

        )



    @classmethod

    def from_config_path(cls, config_path: Path | None = None) -> "AIRuntime":

        return cls(load_runtime_config(config_path))



    @property

    def config(self) -> RuntimeConfig:

        return self._config



    @property

    def capabilities(self) -> CapabilityRegistry | None:

        return self._capabilities



    @property

    def tasks(self) -> TaskRegistry:

        return self._tasks



    @property

    def prompts(self) -> PromptRegistry:

        return self._prompts



    @property

    def schemas(self) -> SchemaRegistry:

        return self._schemas



    @property

    def models(self) -> ModelRegistry:

        return self._models



    @property

    def providers(self) -> ProviderManager:

        return self._providers



    @property

    def health(self) -> HealthMonitor:

        return self._health



    @property

    def metrics(self) -> MetricsCollector:

        return self._metrics



    def run_task(self, task: str, input: str | dict[str, Any], **kwargs: Any):

        """Execute a registered AI task."""

        task_def = self._tasks.get(task)

        if isinstance(input, dict):

            payload = input.get("text") or input.get("input") or str(input)

        else:

            payload = input

        return self._executor.execute(task_def, payload, **kwargs)



    def refresh_health(self) -> list:

        return self._health.refresh_all(self._providers.providers)



    def reload_registries(self) -> None:

        if self._capabilities is not None:

            self._capabilities.reload()

        self._tasks.reload()

        self._prompts.reload()

        self._schemas.reload()

        self._models.reload()





_RUNTIME_LOCK = RLock()

_RUNTIMES: OrderedDict[str, AIRuntime] = OrderedDict()

_MAX_RUNTIMES = 4

_default_runtime: AIRuntime | None = None





def _resolved_config_key(config_path: Path | None = None) -> str:

    from runtime.config.loader import _resolve_config_path

    return str(_resolve_config_path(config_path))





def _close_runtime(runtime: AIRuntime) -> None:

    try:

        for provider in runtime.providers.providers.values():

            closer = getattr(provider, "close", None)

            if closer is not None:

                closer()

    except Exception:

        pass





def reset_runtime() -> None:

    """Drop cached runtimes (tests / explicit reload)."""

    global _default_runtime

    with _RUNTIME_LOCK:

        for runtime in _RUNTIMES.values():

            _close_runtime(runtime)

        _RUNTIMES.clear()

        _default_runtime = None





def get_runtime(config_path: Path | None = None) -> AIRuntime:

    """Return a runtime for the resolved configuration; reuse when the key matches."""

    global _default_runtime

    key = _resolved_config_key(config_path)

    with _RUNTIME_LOCK:

        existing = _RUNTIMES.get(key)

        if existing is not None:

            _RUNTIMES.move_to_end(key)

            _default_runtime = existing

            return existing

        runtime = AIRuntime.from_config_path(config_path)

        while len(_RUNTIMES) >= _MAX_RUNTIMES:

            _old_key, old_runtime = _RUNTIMES.popitem(last=False)

            if old_runtime is not runtime:

                _close_runtime(old_runtime)

        _RUNTIMES[key] = runtime

        _default_runtime = runtime

        return runtime





def run_task(task: str, input: str | dict[str, Any], **kwargs: Any):

    """Module-level convenience API."""

    return get_runtime().run_task(task, input, **kwargs)

