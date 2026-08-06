"""Resolve company_key from staff JWT / hr_signup."""
from __future__ import annotations

from app.database.connection.db import db_get
from app.domains.identity.authorization.rbac import get_user_id
from app.domains.recruitment.services.company_scope import normalize_company


def resolve_company_for_user(user: dict | None) -> tuple[str | None, str | None]:
    """Return (company_key, company_display)."""
    if not user:
        return None, None
    company = (user.get('company') or '').strip()
    if not company:
        uid = get_user_id(user)
        if uid:
            row = db_get('SELECT company FROM hr_signup WHERE hrid = ?', (uid,))
            company = ((row or {}).get('company') or '').strip()
    if not company:
        return None, None
    return normalize_company(company), company


def company_key_from_job(job: dict | None) -> str | None:
    if not job:
        return None
    company = (job.get('company') or job.get('company_name') or '').strip()
    return normalize_company(company) if company else None
