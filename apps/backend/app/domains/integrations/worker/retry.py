"""Retry helpers — exponential backoff, max attempts, dead status."""
from __future__ import annotations

import logging
import time

from app.domains.integrations.config import get_max_retries, get_retry_base_seconds
from app.domains.integrations import repository as repo

logger = logging.getLogger(__name__)


def should_retry(retry_count: int) -> bool:
    return retry_count < get_max_retries()


def backoff_seconds(retry_count: int) -> float:
    base = get_retry_base_seconds()
    return base * (2 ** max(0, retry_count))


def mark_dead(company_key: str, job_id: str, provider: str, error: str | None, retry_count: int) -> None:
    repo.upsert_external_job(
        company_key,
        job_id,
        provider,
        sync_status='dead',
        error_message=error or 'Max retries exceeded',
        retry_count=retry_count,
    )


def sleep_backoff(retry_count: int) -> None:
    delay = backoff_seconds(retry_count)
    if delay > 0:
        time.sleep(min(delay, 30.0))
