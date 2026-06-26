"""AI Runtime boundary — the only module that talks to the runtime."""

from __future__ import annotations

from pathlib import Path

from runtime import RUNTIME_VERSION, get_runtime, run_task
from runtime.interfaces.types import TaskResult


def execute_task(task: str, input_text: str, *, runtime_config_path: Path | None = None) -> TaskResult:
    """Execute an AI task via the runtime."""
    if runtime_config_path is not None:
        get_runtime(runtime_config_path)
    return run_task(task, input_text)


def runtime_version() -> str:
    return RUNTIME_VERSION


def prompt_version(prompt_id: str, *, runtime_config_path: Path | None = None) -> str:
    runtime = get_runtime(runtime_config_path)
    return runtime.prompts.get(prompt_id).version


def schema_version(schema_id: str, *, runtime_config_path: Path | None = None) -> str:
    runtime = get_runtime(runtime_config_path)
    return runtime.schemas.get(schema_id).version


def runtime_metrics_summary(*, runtime_config_path: Path | None = None) -> dict:
    runtime = get_runtime(runtime_config_path)
    return runtime.metrics.summary()
