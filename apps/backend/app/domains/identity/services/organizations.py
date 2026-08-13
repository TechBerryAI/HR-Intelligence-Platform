"""Organization (tenant / company) helpers — slug from company name / company_key."""
from __future__ import annotations

import re

from flask import jsonify

from app.database.connection.db import db_all, db_get, db_run
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


def find_organization_by_slug(slug: str | None) -> dict | None:
    """Return organizations row for slug, or None. Does not create."""
    s = (slug or '').strip().lower()
    if not s:
        return None
    row = db_get('SELECT id, name, slug FROM organizations WHERE slug = ?', (s,))
    return dict(row) if row else None


def get_organization_by_slug(slug: str | None) -> dict | None:
    return find_organization_by_slug(slug)


def get_organization(organization_id: str | None) -> dict | None:
    if not organization_id:
        return None
    try:
        row = db_get(
            'SELECT id, name, slug FROM organizations WHERE id = ?',
            (str(organization_id),),
        )
    except Exception:
        return None
    return dict(row) if row else None


def organization_exists_for_name(name: str | None) -> bool:
    """True if an org already exists for this company name's slug."""
    slug = slugify_company(name)
    if not slug or slug == 'org':
        return False
    return bool(db_get('SELECT id FROM organizations WHERE slug = ?', (slug,)))


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


def force_organization_id(table: str, pk_col: str, pk_val, organization_id: str | None) -> None:
    """Set organization_id even if already set (e.g. admin create)."""
    if not organization_id or not table or not pk_col or pk_val is None:
        return
    allowed = {
        'hr_signup': 'hrid',
        'jobs': 'jdid',
    }
    if table not in allowed or allowed[table] != pk_col:
        return
    db_run(
        f'UPDATE {table} SET organization_id = ? WHERE {pk_col} = ?',
        (organization_id, pk_val),
    )


def get_organization_id_for_user(user: dict | None) -> str | None:
    """Resolve org from DB first; JWT claim is a last-resort fallback only."""
    if not user:
        return None
    from app.domains.identity.authorization.rbac import get_user_id

    uid = get_user_id(user)
    if uid:
        row = db_get('SELECT organization_id, company FROM hr_signup WHERE hrid = ?', (uid,))
        if row:
            if row.get('organization_id'):
                return str(row['organization_id'])
            org_id = ensure_organization(row.get('company'))
            if org_id:
                attach_organization_id('hr_signup', 'hrid', uid, org_id)
                return org_id
    claimed = user.get('organization_id')
    if claimed:
        return str(claimed)
    return None


def require_organization_id(user: dict | None) -> tuple[str | None, tuple | None]:
    """
    Resolve caller's organization_id.
    Returns (org_id, None) on success, or (None, (jsonify_response, status)).
    """
    org_id = get_organization_id_for_user(user)
    if not org_id:
        return None, (jsonify({'error': 'No company assigned to this account'}), 403)
    return org_id, None


def list_companies_with_enabled_jobs() -> list[dict]:
    """Public picker: orgs that have at least one enabled job."""
    rows = db_all(
        """
        SELECT DISTINCT o.id, o.name, o.slug
        FROM organizations o
        INNER JOIN jobs j ON j.organization_id = o.id
        WHERE (j.enabled = true OR j.enabled IS NULL)
        ORDER BY o.name ASC
        """,
        (),
    )
    return [
        {'id': str(r['id']), 'name': r.get('name') or '', 'slug': r.get('slug') or ''}
        for r in (rows or [])
    ]


def resolve_public_organization(slug: str | None = None) -> dict | None:
    """
    Resolve the company for the public job board without prompting the user.

    Order:
      1. Explicit slug (?company= / path)
      2. DEFAULT_PUBLIC_COMPANY_SLUG env
      3. Sole organization that currently has enabled jobs
    """
    import os

    explicit = (slug or '').strip().lower()
    if explicit:
        return find_organization_by_slug(explicit)

    default_slug = (os.getenv('DEFAULT_PUBLIC_COMPANY_SLUG') or '').strip().lower()
    if default_slug:
        org = find_organization_by_slug(default_slug)
        if org:
            return org

    companies = list_companies_with_enabled_jobs()
    if len(companies) == 1:
        return find_organization_by_slug(companies[0].get('slug'))
    if len(companies) == 0:
        # Fall back to sole organization row even if no enabled jobs yet
        rows = db_all('SELECT id, name, slug FROM organizations ORDER BY created_at ASC LIMIT 2', ())
        if rows and len(rows) == 1:
            return dict(rows[0])
    return None


def enrich_signup_with_org(signup_data: dict | None) -> dict:
    """Ensure signup row dict has organization_id (lazy attach) and org slug/name."""
    if not signup_data:
        return {}
    data = dict(signup_data)
    org_id = data.get('organization_id')
    if not org_id:
        org_id = ensure_organization(data.get('company'))
        if org_id and data.get('hrid'):
            attach_organization_id('hr_signup', 'hrid', data['hrid'], org_id)
        data['organization_id'] = org_id
    else:
        data['organization_id'] = str(org_id)
    org = get_organization(data.get('organization_id'))
    if org:
        data['org_slug'] = org.get('slug')
        data['org_name'] = org.get('name')
        if not data.get('company'):
            data['company'] = org.get('name')
    return data
