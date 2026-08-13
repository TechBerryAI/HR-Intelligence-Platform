"""Task execution engine with retry and fallback."""



from __future__ import annotations



import time

from typing import Any



from runtime.config.models import RuntimeConfig, TaskDefinition

from runtime.exceptions import (

    ProviderError,

    RetryExhaustedError,

    ValidationError,

)

from runtime.health.monitor import HealthMonitor

from runtime.interfaces.types import InferenceRequest, TaskContext, TaskResult

from runtime.metrics.collector import MetricsCollector, TaskMetric

from providers.manager import ProviderManager

from runtime.registry.capability_registry import CapabilityRegistry

from runtime.registry.model_registry import ModelRegistry

from runtime.registry.prompt_registry import PromptRegistry

from runtime.registry.schema_registry import SchemaRegistry

from runtime.utils.retry import RetryPolicy, sleep_backoff

from runtime.validation.validator import OutputValidator





class TaskExecutor:

    """Execute tasks with provider fallback, retry, and validation."""



    def __init__(

        self,

        *,

        config: RuntimeConfig,

        provider_manager: ProviderManager,

        prompt_registry: PromptRegistry,

        schema_registry: SchemaRegistry,

        model_registry: ModelRegistry,

        health_monitor: HealthMonitor,

        metrics: MetricsCollector,

        capability_registry: CapabilityRegistry | None = None,

        validator: OutputValidator | None = None,

    ) -> None:

        self._config = config

        self._providers = provider_manager

        self._prompts = prompt_registry

        self._schemas = schema_registry

        self._models = model_registry

        self._capabilities = capability_registry

        self._health = health_monitor

        self._metrics = metrics

        self._validator = validator or OutputValidator()

        self._retry = RetryPolicy(

            max_attempts=config.retry.max_attempts,

            backoff_seconds=config.retry.backoff_seconds,

            retry_on_status=tuple(config.retry.retry_on_status),

        )



    def execute(self, task: TaskDefinition, input_data: str, **kwargs: Any) -> TaskResult:

        capability = self._resolve_capability(task.name)

        runtime_config = capability.runtime_config if capability else None



        input_text = self._prepare_input(input_data)

        provider_chain = self._providers.get_provider_chain(task)

        schema = self._schemas.resolve(task.schema_id)

        prompt_text = self._prompts.resolve(task.prompt_id, variables={"input": input_text})



        temperature = kwargs.get("temperature", task.temperature)

        max_tokens = kwargs.get("max_tokens", task.max_tokens)

        timeout_seconds = kwargs.get("timeout_seconds", self._config.settings.default_timeout_seconds)

        if runtime_config is not None:

            if "temperature" not in kwargs:

                temperature = runtime_config.temperature

            if "max_tokens" not in kwargs:

                max_tokens = runtime_config.max_tokens

            if runtime_config.timeout_seconds is not None and "timeout_seconds" not in kwargs:

                timeout_seconds = runtime_config.timeout_seconds



        max_attempts = self._retry.max_attempts

        if runtime_config is not None and runtime_config.retries is not None:

            max_attempts = max(1, runtime_config.retries + 1)

        if kwargs.get("max_attempts") is not None:

            max_attempts = max(1, int(kwargs["max_attempts"]))

        elif kwargs.get("retries") is not None:

            max_attempts = max(1, int(kwargs["retries"]) + 1)



        attempts = 0

        retries = 0

        fallbacks_used = 0

        validation_failures = 0

        last_error: Exception | None = None

        start = time.perf_counter()



        for attempt in range(1, max_attempts + 1):

            attempts = attempt

            for index, provider in enumerate(provider_chain):

                if index > 0:

                    fallbacks_used += 1

                resolved_model = self._models.resolve(task.model_alias, provider_id=provider.provider_id)

                request = InferenceRequest(

                    task=task.name,

                    prompt=prompt_text,

                    input_text=input_text,

                    model=resolved_model,

                    schema_id=task.schema_id,

                    temperature=temperature,

                    max_tokens=max_tokens,

                    timeout_seconds=timeout_seconds,

                    metadata={
                        "attempt": attempt,
                        "json_schema": schema,
                        **kwargs.get("metadata", {}),
                    },

                )

                try:

                    response = provider.complete(request)

                    self._health.record_success(provider.provider_id, latency_ms=response.latency_ms)

                    try:

                        output = self._validator.validate(

                            response.content,

                            schema=schema,

                            rules=task.validation,

                        )

                    except ValidationError as exc:

                        validation_failures += 1

                        self._metrics.record_task(

                            TaskMetric(

                                task=task.name,

                                provider_id=provider.provider_id,

                                model=resolved_model,

                                duration_ms=(time.perf_counter() - start) * 1000.0,

                                success=False,

                                attempts=attempts,

                                fallbacks_used=fallbacks_used,

                                validation_failures=validation_failures,

                                retries=retries,

                            )

                        )

                        if self._config.validation.fail_on_validation_error:

                            if attempt < max_attempts:

                                retries += 1

                                sleep_backoff(attempt, self._retry.backoff_seconds)

                                break

                            raise

                        output = response.content



                    duration_ms = (time.perf_counter() - start) * 1000.0

                    self._metrics.record_task(

                        TaskMetric(

                            task=task.name,

                            provider_id=provider.provider_id,

                            model=resolved_model,

                            duration_ms=duration_ms,

                            success=True,

                            attempts=attempts,

                            fallbacks_used=fallbacks_used,

                            validation_failures=validation_failures,

                            retries=retries,

                            token_usage=response.token_usage,

                        )

                    )

                    return TaskResult(

                        task=task.name,

                        output=output,

                        raw_content=response.content,

                        provider_id=provider.provider_id,

                        model=resolved_model,

                        prompt_id=task.prompt_id,

                        schema_id=task.schema_id,

                        latency_ms=duration_ms,

                        attempts=attempts,

                        retries=retries,

                        fallbacks_used=fallbacks_used,

                        validation_passed=validation_failures == 0,

                        token_usage=response.token_usage,

                        metadata={

                            "context": TaskContext(

                                task=task.name,

                                prompt_id=task.prompt_id,

                                schema_id=task.schema_id,

                                model_alias=task.model_alias,

                                resolved_model=resolved_model,

                                provider_id=provider.provider_id,

                                prompt_text=prompt_text,

                                validation_rules=task.validation,

                            ).__dict__,

                            "capability_id": task.name,

                            "capability_version": capability.metadata.version if capability else None,

                            "output_mode": runtime_config.output_mode if runtime_config else None,

                        },

                    )

                except ProviderError as exc:

                    last_error = exc

                    self._health.record_failure(provider.provider_id, str(exc))

                    if exc.retryable and (

                        self._retry.should_retry_status(exc.status_code) or exc.status_code is None

                    ):

                        if attempt < max_attempts:

                            retries += 1

                            sleep_backoff(attempt, self._retry.backoff_seconds)

                            break

                    continue

                except ValidationError:

                    raise



            else:

                continue

            continue



        duration_ms = (time.perf_counter() - start) * 1000.0

        self._metrics.record_task(

            TaskMetric(

                task=task.name,

                provider_id=provider_chain[-1].provider_id if provider_chain else "unknown",

                model=task.model_alias,

                duration_ms=duration_ms,

                success=False,

                attempts=attempts,

                fallbacks_used=fallbacks_used,

                validation_failures=validation_failures,

                retries=retries,

            )

        )

        message = str(last_error) if last_error else "Task execution failed"

        raise RetryExhaustedError(message, attempts=attempts) from last_error



    def _resolve_capability(self, task_name: str):

        if self._capabilities is None:

            return None

        if not self._capabilities.has(task_name):

            return None

        return self._capabilities.get(task_name)



    def _prepare_input(self, input_data: str) -> str:

        max_chars = self._config.settings.max_input_chars

        if max_chars > 0 and len(input_data) > max_chars:

            return input_data[:max_chars]

        return input_data

