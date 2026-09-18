"""Map internal job rows to JobSnapshot (never expose raw jobs to providers)."""
from __future__ import annotations

from app.domains.integrations.company_context import company_key_from_job
from app.domains.integrations.dto import JobSnapshot
from app.domains.recruitment.services.company_scope import normalize_company


def job_row_to_snapshot(
    job: dict,
    organization_id: str | None = None,
    *,
    company_key: str | None = None,
) -> JobSnapshot:
    """organization_id is the tenant boundary; falls back to job['organization_id']
    from the DB row. company_key is display metadata only — never a lookup key.
    """
    org_id = organization_id or job.get('organization_id')
    key = company_key or company_key_from_job(job) or normalize_company(job.get('company') or '')
    enabled = job.get('enabled')
    if enabled is None:
        enabled_flag = True
    else:
        enabled_flag = bool(enabled)
    return JobSnapshot(
        job_id=str(job.get('jdid') or job.get('job_id') or ''),
        title=(job.get('title') or '').strip(),
        company=(job.get('company') or job.get('company_name') or '').strip(),
        organization_id=str(org_id) if org_id else '',
        company_key=key or '',
        location=(job.get('location') or None),
        salary=(job.get('salary') or None),
        experience=(job.get('experience') or None),
        description=(job.get('description') or None),
        keywords=(job.get('keywords') or None),
        enabled=enabled_flag,
        posted_on=job.get('posted_on') or job.get('postedOn'),
    )
