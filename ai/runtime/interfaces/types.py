"""Shared runtime data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class InferenceRequest:
    """Provider-agnostic inference request."""

    task: str
    prompt: str
    input_text: str
    model: str
    schema_id: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceResponse:
    """Provider-agnostic inference response."""

    content: str
    provider_id: str
    model: str
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] | None = None


@dataclass
class ProviderHealth:
    """Provider health snapshot."""

    provider_id: str
    available: bool
    latency_ms: float | None = None
    failure_count: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    checked_at: datetime | None = None


@dataclass(frozen=True)
class TaskContext:
    """Resolved execution context for a task."""

    task: str
    prompt_id: str
    schema_id: str
    model_alias: str
    resolved_model: str
    provider_id: str
    prompt_text: str
    validation_rules: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Final result returned to application code."""

    task: str
    output: Any
    raw_content: str
    provider_id: str
    model: str
    prompt_id: str
    schema_id: str
    latency_ms: float
    attempts: int = 1
    retries: int = 0
    fallbacks_used: int = 0
    validation_passed: bool = True
    token_usage: dict[str, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
