"""Future webhook intake scaffold.

Not yet wired to an inbound route. When wired, the caller MUST resolve
``organization_id`` from a trusted provider/integration identifier (e.g. the
``integration_provider`` row the webhook's API key/signature maps to) —
never from a company name in the payload. See BUG-004.
"""
from __future__ import annotations

from app.domains.integrations import repository as repo


def record_webhook(
    provider: str,
    payload: dict | None = None,
    *,
    organization_id: str | None = None,
    company_key: str | None = None,
    event_type: str | None = None,
    headers: dict | None = None,
) -> int | None:
    return repo.insert_webhook_event(
        provider,
        organization_id=organization_id,
        company_key=company_key,
        event_type=event_type,
        payload=payload,
        headers_json=headers,
    )
