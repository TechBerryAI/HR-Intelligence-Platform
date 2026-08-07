"""Organization (tenant) helpers — slug from company name / company_key."""
from __future__ import annotations

import re

from app.database.connection.db import db_get, db_run
from app.domains.recruitment.services.company_scope import normalize_company


def slugify_company(name: str | None) -> str:
    base = normalize_company(name) or (name or '').strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
    return slug or 'org'


def ensure_organization(name: str | None, *, company_key: str | None = None) -> str | None:
    """
    Find or create an organizations row. Returns organization UUID or None.
    """
    display = (name or company_key or '').strip()
    slug = slugify_company(company_key or name)
    if not slug or slug == 'org' and not display:
        return None
    existing = db_get('SELECT id FROM organizations WHERE slug = ?', (slug,))
    if existing:
        return str(existing['id'])
    row = db_get(
        """
        INSERT INTO organizations (name, slug)
        VALUES (?, ?)
        ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (display or slug, slug),
    )
    return str(row['id']) if row else None


def attach_organization_id(table: str, pk_col: str, pk_val, organization_id: str | None) -> None:
    if not organization_id or not table or not pk_col or pk_val is None:
        return
    # Whitelist tables to avoid SQL injection via table/column names
    allowed = {
        'hr_signup': 'hrid',
        'jobs': 'jdid',
        'integration_provider': 'id',
        'external_jobs': 'id',
        'external_applications': 'id',
        'oauth_tokens': 'id',
    }
    if table not in allowed or allowed[table] != pk_col:
        return
    db_run(
        f'UPDATE {table} SET organization_id = ? WHERE {pk_col} = ? AND organization_id IS NULL',
        (organization_id, pk_val),
    )


def get_organization_id_for_user(user: dict | None) -> str | None:
    if not user:
        return None
    from app.domains.identity.authorization.rbac import get_user_id

    uid = get_user_id(user)
    if not uid:
        return None
    row = db_get('SELECT organization_id, company FROM hr_signup WHERE hrid = ?', (uid,))
    if not row:
        return None
    if row.get('organization_id'):
        return str(row['organization_id'])
    org_id = ensure_organization(row.get('company'))
    if org_id:
        attach_organization_id('hr_signup', 'hrid', uid, org_id)
    return org_id
