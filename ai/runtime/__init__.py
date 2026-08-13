"""AI Runtime — central orchestration layer for all AI capabilities.

Package exports are lazy so `from runtime.exceptions import ...` does not
import the executor → provider factory cycle.
"""

from __future__ import annotations

RUNTIME_VERSION = "1.0.0"

__all__ = ["AIRuntime", "RUNTIME_VERSION", "get_runtime", "run_task"]


def __getattr__(name: str):
    if name in {"AIRuntime", "get_runtime", "run_task"}:
        from runtime.core.runtime import AIRuntime, get_runtime, run_task

        mapping = {
            "AIRuntime": AIRuntime,
            "get_runtime": get_runtime,
            "run_task": run_task,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
