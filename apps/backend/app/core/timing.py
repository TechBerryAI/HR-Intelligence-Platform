"""Reusable execution-time instrumentation for HRIP pipeline stages."""
from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _safe_bind_ids(func: Callable[..., Any], args: tuple, kwargs: dict) -> None:
    """Pull candidate_id / job_id / user_id from decorated call args when present."""
    try:
        from app.core.developer_mode import is_developer_mode_enabled
        from app.core.request_context import update_timing_ids

        if not is_developer_mode_enabled():
            return
        try:
            bound = inspect.signature(func).bind_partial(*args, **kwargs)
            bound.apply_defaults()
            params = bound.arguments
        except Exception:
            params = dict(kwargs)
        cand = params.get("candidate_id") or params.get("cid")
        job = params.get("job_id") or params.get("jdid") or params.get("jd_id")
        user = params.get("uploader_id") or params.get("user_id")
        update_timing_ids(
            candidate_id=str(cand) if cand is not None else None,
            job_id=str(job) if job is not None else None,
            user_id=str(user) if user is not None else None,
        )
    except Exception:
        pass


def _flask_user_id() -> Optional[str]:
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return None
        user = getattr(request, "user", None)
        if isinstance(user, dict):
            return user.get("user_id")
    except Exception:
        return None
    return None


def timing(func: F) -> F:
    """
    Log wall-clock duration of ``func`` in milliseconds (INFO).

    Uses ``time.perf_counter()``, preserves metadata via ``functools.wraps``,
    and always logs in a ``finally`` block (including when exceptions occur).

    When Developer Mode is enabled, also records the event in the in-memory
    timing collector (no business-logic side effects).
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)
        start = time.perf_counter()
        success = True
        exc_name: Optional[str] = None
        depth = 0

        try:
            from app.core.developer_mode import is_developer_mode_enabled
            from app.core.request_context import (
                pop_timing_depth,
                push_timing_depth,
                update_timing_ids,
            )

            collect = is_developer_mode_enabled()
        except Exception:
            collect = False

        if collect:
            try:
                depth = push_timing_depth()
                _safe_bind_ids(func, args, kwargs)
                uid = _flask_user_id()
                if uid:
                    update_timing_ids(user_id=uid)
            except Exception:
                pass

        try:
            return func(*args, **kwargs)
        except Exception as exc:
            success = False
            exc_name = type(exc).__name__
            raise
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
                    "success": success,
                    "exception": exc_name,
                },
            )
            if collect:
                try:
                    from app.core.timing_collector import make_timing_event, timing_collector

                    event = make_timing_event(
                        function=func.__qualname__,
                        module=func.__module__,
                        duration_ms=duration_ms,
                        success=success,
                        exception_name=exc_name,
                        depth=depth,
                    )
                    timing_collector.record(event)
                except Exception:
                    pass
                try:
                    pop_timing_depth()
                except Exception:
                    pass

    return wrapper  # type: ignore[return-value]
