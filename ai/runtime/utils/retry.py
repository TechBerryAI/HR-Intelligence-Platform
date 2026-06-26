"""Retry helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration."""

    max_attempts: int = 3
    backoff_seconds: float = 2.0
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)

    def should_retry_status(self, status_code: int | None) -> bool:
        if status_code is None:
            return False
        return status_code in self.retry_on_status


def sleep_backoff(attempt: int, backoff_seconds: float) -> None:
    """Exponential backoff sleep between attempts."""
    if attempt <= 0:
        return
    time.sleep(backoff_seconds * (2 ** (attempt - 1)))
