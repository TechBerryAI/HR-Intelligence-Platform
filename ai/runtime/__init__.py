"""AI Runtime — central orchestration layer for all AI capabilities."""

from __future__ import annotations

from runtime.core.runtime import AIRuntime, get_runtime, run_task

RUNTIME_VERSION = "1.0.0"

__all__ = ["AIRuntime", "RUNTIME_VERSION", "get_runtime", "run_task"]
