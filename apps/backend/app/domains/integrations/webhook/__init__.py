"""Future webhook intake scaffold."""
from __future__ import annotations

from app.domains.integrations import repository as repo


def record_webhook(
    provider: str,
    payload: dict | None = None,
    *,
    company_key: str | None = None,
    event_type: str | None = None,
    headers: dict | None = None,
) -> int | None:
    return repo.insert_webhook_event(
        provider,
        company_key=company_key,
        event_type=event_type,
        payload=payload,
        headers_json=headers,
    )
