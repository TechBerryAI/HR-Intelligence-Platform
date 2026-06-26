"""Runtime metrics collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class TaskMetric:
    task: str
    provider_id: str
    model: str
    duration_ms: float
    success: bool
    attempts: int
    fallbacks_used: int
    validation_failures: int
    retries: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    token_usage: dict[str, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """In-memory metrics store (future: export to monitoring backend)."""

    def __init__(self) -> None:
        self._events: list[TaskMetric] = []

    @property
    def events(self) -> list[TaskMetric]:
        return list(self._events)

    def record_task(self, metric: TaskMetric) -> None:
        self._events.append(metric)

    def summary(self) -> dict[str, Any]:
        total = len(self._events)
        if total == 0:
            return {
                "total_tasks": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "fallbacks": 0,
                "validation_failures": 0,
                "retries": 0,
                "by_provider": {},
            }

        successes = sum(1 for event in self._events if event.success)
        by_provider: dict[str, dict[str, float | int]] = {}
        for event in self._events:
            bucket = by_provider.setdefault(
                event.provider_id,
                {"count": 0, "successes": 0, "duration_ms": 0.0},
            )
            bucket["count"] = int(bucket["count"]) + 1
            bucket["successes"] = int(bucket["successes"]) + (1 if event.success else 0)
            bucket["duration_ms"] = float(bucket["duration_ms"]) + event.duration_ms

        return {
            "total_tasks": total,
            "success_rate": successes / total,
            "avg_duration_ms": sum(event.duration_ms for event in self._events) / total,
            "fallbacks": sum(event.fallbacks_used for event in self._events),
            "validation_failures": sum(event.validation_failures for event in self._events),
            "retries": sum(event.retries for event in self._events),
            "by_provider": by_provider,
        }

    def reset(self) -> None:
        self._events.clear()
