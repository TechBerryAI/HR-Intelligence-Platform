"""LinkedIn Job Posting API foundation payload (official schema).

Source: https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/job-posting-api-schema
Versioned endpoint uses listingType BASIC and jobPostingOperationType CREATE|UPDATE|CLOSE|RENEW.
externalJobPostingId is the partner-system unique id (max 75 chars) — not a LinkedIn-assigned id.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from app.domains.integrations.dto import JobSnapshot, ProviderConfig

_OPS = frozenset({'CREATE', 'UPDATE', 'CLOSE', 'RENEW'})


def linkedin_external_posting_id(job_id: str) -> str:
    """Stable partner correlation id. Same job always yields the same value (max 75)."""
    raw = (job_id or '').strip()
    if not raw:
        raise ValueError('job_id is required for LinkedIn externalJobPostingId')
    key = f'hcip:{raw}'
    if len(key) <= 75:
        return key
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return f'hcip:{digest[:69]}'


def _listed_at_ms(job: JobSnapshot) -> int:
    posted = getattr(job, 'posted_on', None)
    if posted is not None:
        if isinstance(posted, datetime):
            dt = posted if posted.tzinfo else posted.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        if isinstance(posted, (int, float)):
            value = int(posted)
            return value if value > 10_000_000_000 else value * 1000
        if isinstance(posted, str) and posted.strip():
            try:
                dt = datetime.fromisoformat(posted.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                pass
    return int(time.time() * 1000)


def to_linkedin_payload(
    job: JobSnapshot,
    config: ProviderConfig | None,
    *,
    operation: str,
    external_job_posting_id: str | None = None,
) -> dict[str, Any]:
    op = (operation or 'CREATE').strip().upper()
    if op not in _OPS:
        raise ValueError(f'Unsupported LinkedIn jobPostingOperationType: {operation}')
    settings = dict((config.settings if config else None) or {})
    posting_id = (external_job_posting_id or linkedin_external_posting_id(job.job_id)).strip()
    if not posting_id or len(posting_id) > 75:
        raise ValueError('externalJobPostingId must be 1–75 characters')

    apply_url = (
        (settings.get('companyApplyUrl') or settings.get('company_apply_url') or '')
        .strip()
    )
    payload: dict[str, Any] = {
        'externalJobPostingId': posting_id,
        'jobPostingOperationType': op,
        'title': (job.title or '')[:200],
        'description': job.description or job.title or '',
        'listedAt': _listed_at_ms(job),
        'listingType': 'BASIC',
        'workplaceTypes': ['On-site'],
        'companyJobCode': posting_id,
    }
    location = (job.location or '').strip()
    if location:
        payload['location'] = location
    if apply_url:
        payload['companyApplyUrl'] = apply_url

    company_urn = (
        settings.get('companyUrn')
        or settings.get('company_urn')
        or settings.get('integrationContext')
        or settings.get('company')
        or ''
    )
    company_urn = str(company_urn).strip()
    if company_urn.startswith('urn:li:'):
        payload['company'] = company_urn
    else:
        page_url = (settings.get('companyPageUrl') or settings.get('company_page_url') or '').strip()
        if page_url:
            payload['companyPageUrl'] = page_url
        elif job.company:
            payload['companyName'] = job.company

    poster = (settings.get('posterEmail') or settings.get('poster_email') or '').strip()
    if poster:
        payload['posterEmail'] = poster
    return payload
