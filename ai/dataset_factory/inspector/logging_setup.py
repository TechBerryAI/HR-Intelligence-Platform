"""Structured logging setup for Dataset Inspector."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.logging import RichHandler

if TYPE_CHECKING:
    from .config import InspectorConfig
    from .models import InspectionResult, LogEvent


console = Console(stderr=True)


class InspectionEventCollector(logging.Handler):
    """Collect structured log events for inspection_log.yaml."""

    def __init__(self, events: list[LogEvent]) -> None:
        super().__init__()
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:
        from .models import LogEvent
        from .utils import utc_now

        details = getattr(record, "details", None)
        event = LogEvent(
            timestamp=utc_now(),
            level=record.levelname.lower(),
            message=record.getMessage(),
            phase_id=getattr(record, "phase_id", None),
            code=getattr(record, "code", None),
            path=getattr(record, "path", None),
            details=details if isinstance(details, dict) else None,
        )
        self.events.append(event)


def setup_logging(config: InspectorConfig, events: list[LogEvent]) -> logging.Logger:
    """Configure application logger with Rich and event collection."""
    logger = logging.getLogger("dataset_inspector")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    logger.propagate = False

    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=config.verbose,
        markup=False,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    logger.addHandler(rich_handler)

    collector = InspectionEventCollector(events)
    collector.setLevel(logging.WARNING)
    logger.addHandler(collector)

    return logger


def log_phase(logger: logging.Logger, phase_id: str, message: str) -> None:
    """Log an info message tagged with a phase id."""
    logger.info(message, extra={"phase_id": phase_id})


def log_file_issue(
    logger: logging.Logger,
    *,
    level: int,
    phase_id: str,
    code: str,
    path: str,
    message: str,
    details: dict | None = None,
) -> None:
    """Log a per-file issue without stopping inspection."""
    logger.log(
        level,
        message,
        extra={"phase_id": phase_id, "code": code, "path": path, "details": details},
    )


def log_summary(logger: logging.Logger, result: InspectionResult) -> None:
    """Print execution summary to the console."""
    logger.info(
        "Inspection complete — files=%d errors=%d warnings=%d elapsed=%.2fs",
        len(result.files),
        result.errors,
        result.warnings,
        result.duration_seconds,
    )
