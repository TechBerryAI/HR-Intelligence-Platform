"""Request-scoped context for timing correlation (Developer Mode)."""
from __future__ import annotations

import contextvars
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

_ctx: contextvars.ContextVar[Optional["TimingRequestContext"]] = contextvars.ContextVar(
    "timing_request_context",
    default=None,
)


@dataclass
class TimingRequestContext:
    request_id: str
    started_at: float  # perf_counter
    started_at_iso: str
    path: str = ""
    method: str = ""
    user_id: Optional[str] = None
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def get_timing_context() -> Optional[TimingRequestContext]:
    return _ctx.get()


def set_timing_context(ctx: Optional[TimingRequestContext]) -> contextvars.Token:
    return _ctx.set(ctx)


def reset_timing_context(token: contextvars.Token) -> None:
    _ctx.reset(token)


def update_timing_ids(
    *,
    user_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> None:
    """Merge identity fields into the active request context (no-op if none)."""
    ctx = _ctx.get()
    if ctx is None:
        return
    if user_id is not None and user_id != "":
        ctx.user_id = str(user_id)
    if candidate_id is not None and candidate_id != "":
        ctx.candidate_id = str(candidate_id)
    if job_id is not None and job_id != "":
        ctx.job_id = str(job_id)


def mark_pipeline_stage_start(stage: str) -> None:
    """Record wall-clock start for a Document Intelligence engine stage."""
    ctx = _ctx.get()
    if ctx is None or not stage:
        return
    ctx.meta.setdefault("stage_starts", {})[stage] = time.perf_counter()


def take_pipeline_stage_elapsed_ms(stage: str) -> Optional[float]:
    """Return ms since stage start (and clear the start mark), or None."""
    ctx = _ctx.get()
    if ctx is None or not stage:
        return None
    starts = ctx.meta.get("stage_starts") or {}
    started = starts.pop(stage, None)
    if started is None:
        return None
    return (time.perf_counter() - started) * 1000.0


def start_request_context(
    *,
    path: str = "",
    method: str = "",
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> TimingRequestContext:
    from datetime import datetime, timezone

    ctx = TimingRequestContext(
        request_id=request_id or new_request_id(),
        started_at=time.perf_counter(),
        started_at_iso=datetime.now(timezone.utc).isoformat(),
        path=path or "",
        method=method or "",
        user_id=str(user_id) if user_id else None,
    )
    _ctx.set(ctx)
    return ctx


# Depth counter for nested @timing calls (per context / thread)
_depth: contextvars.ContextVar[int] = contextvars.ContextVar("timing_call_depth", default=0)
_depth_lock = threading.Lock()


def push_timing_depth() -> int:
    depth = _depth.get() + 1
    _depth.set(depth)
    return depth


def pop_timing_depth() -> int:
    depth = max(0, _depth.get() - 1)
    _depth.set(depth)
    return depth


def current_timing_depth() -> int:
    return _depth.get()


def run_in_timing_context(ctx: TimingRequestContext, fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    """
    Run ``fn`` with ``ctx`` bound — for ThreadPool / SSE workers.

    Flask SSE parse endpoints run Document Intelligence in a worker thread;
    contextvars do not propagate automatically, so timings would otherwise
    land under orphan request ids and never appear on the dashboard.
    """
    token = set_timing_context(ctx)
    depth_token = _depth.set(0)
    try:
        return fn(*args, **kwargs)
    finally:
        try:
            _depth.reset(depth_token)
        except Exception:
            _depth.set(0)
        try:
            reset_timing_context(token)
        except Exception:
            set_timing_context(None)
