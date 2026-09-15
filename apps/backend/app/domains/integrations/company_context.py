"""Resolve tenant context (organization_id) from staff JWT / hr_signup.

``organization_id`` is the authoritative tenant boundary (see BUG-004).
``company_key``/``company_display`` are name-derived and must only be used
for display or backward-compatible reporting — never for authorization or
data-scoping decisions, since two unrelated organizations can share (or
normalize to) the same company name.
"""
from __future__ import annotations

from app.database.connection.db import db_get
from app.domains.identity.authorization.rbac import get_user_id
from app.domains.recruitment.services.company_scope import normalize_company


def resolve_organization_for_user(user: dict | None) -> tuple[str | None, str | None]:
    """Return (organization_id, company_display). Trusted, server-side only.

    organization_id is resolved via ``get_organization_id_for_user`` (DB-first,
    JWT-claim fallback) — never derived from a client-supplied company name.
    """
    if not user:
        return None, None
    from app.domains.identity.services.organizations import get_organization_id_for_user

    org_id = get_organization_id_for_user(user)
    company = (user.get('company') or '').strip()
    if not company:
        uid = get_user_id(user)
        if uid:
            row = db_get('SELECT company FROM hr_signup WHERE hrid = ?', (uid,))
            company = ((row or {}).get('company') or '').strip()
    return org_id, (company or None)


def resolve_company_for_user(user: dict | None) -> tuple[str | None, str | None]:
    """Return (company_key, company_display). DISPLAY METADATA ONLY.

    Do not use the returned company_key for authorization or as a tenant
    lookup key — use ``resolve_organization_for_user`` instead.
    """
    org_id, company = resolve_organization_for_user(user)
    if not company:
        return None, None
    return normalize_company(company), company


def company_key_from_job(job: dict | None) -> str | None:
    """DISPLAY METADATA ONLY — use job['organization_id'] for tenant scoping."""
    if not job:
        return None
    company = (job.get('company') or job.get('company_name') or '').strip()
    return normalize_company(company) if company else None
