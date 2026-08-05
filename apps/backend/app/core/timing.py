"""Reusable execution-time instrumentation for HRIP pipeline stages."""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def timing(func: F) -> F:
    """
    Log wall-clock duration of ``func`` in milliseconds (INFO).

    Uses ``time.perf_counter()``, preserves metadata via ``functools.wraps``,
    and always logs in a ``finally`` block (including when exceptions occur).
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            # Note: LogRecord already defines ``module``; use ``func_module`` in extra.
            logger.info(
                "[TIMING] %s.%s completed in %.2f ms",
                func.__module__,
                func.__qualname__,
                duration_ms,
                extra={
                    "event": "function_timing",
                    "function": func.__qualname__,
                    "func_module": func.__module__,
                    "duration_ms": round(duration_ms, 2),
                },
            )

    return wrapper  # type: ignore[return-value]
