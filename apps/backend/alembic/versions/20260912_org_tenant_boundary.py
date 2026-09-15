"""BUG-004: make organization_id the authoritative tenant boundary for
integrations tables (integration_provider, external_jobs,
external_applications, sync_logs, oauth_tokens).

Previously these tables scoped lookups/uniqueness by ``company_key`` — a
lowercased, suffix-stripped company *name*. Two unrelated organizations with
the same or a similar-looking name normalize to the same company_key and
would collide (share provider credentials, OAuth tokens, ATS sync state).

This migration:
  1. Adds ``oauth_tokens.hrid`` (the column the application code already
     queries/writes — it was missing from the schema, so every OAuth
     calendar connect/refresh has been failing with UndefinedColumn since
     the ``hrid``-based lookup was added to the code).
  2. Backfills ``organization_id`` from ``company_key`` (via the same
     normalization the app used to create ``organizations.slug``) wherever
     it is NULL and the match is *unambiguous* (exactly one organization).
  3. Aborts (raises, rolling back the whole migration) if any row is left
     with organization_id unresolved — this must never silently guess.
  4. Makes organization_id NOT NULL on all 5 tables.
  5. Replaces company_key-scoped uniqueness with organization_id-scoped
     uniqueness (and hrid-scoped for oauth_tokens, which is genuinely
     per-recruiter, not per-organization).

Revision ID: 20260912_org_tenant_boundary
Revises: 20260911_hrid_seq
Create Date: 2026-09-12
"""
from __future__ import annotations

import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '20260912_org_tenant_boundary'
down_revision: Union[str, Sequence[str], None] = '20260911_hrid_seq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SUFFIXES = (
    ' private limited', ' pvt. ltd.', ' pvt ltd.', ' pvt. ltd', ' pvt ltd',
    ' ltd.', ' ltd', ' inc.', ' inc', ' llc',
)


def _normalize_company(name: str | None) -> str:
    """Mirrors app.domains.recruitment.services.company_scope.normalize_company —
    duplicated here so this migration stays correct even if that function
    changes later.
    """
    s = (name or '').strip().lower()
    for suffix in _SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip(' ,.-')
            break
    return s


def _slugify(name: str | None) -> str:
    """Mirrors app.domains.identity.services.organizations.slugify_company."""
    base = _normalize_company(name)
    slug = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
    return slug or 'org'


_TABLES = ('integration_provider', 'external_jobs', 'external_applications', 'sync_logs', 'oauth_tokens')


def _backfill_organization_id(bind, table: str) -> None:
    rows = bind.execute(
        text(f'SELECT DISTINCT company_key FROM {table} WHERE organization_id IS NULL')
    ).fetchall()
    for (company_key,) in rows:
        slug = _slugify(company_key)
        matches = bind.execute(
            text('SELECT id FROM organizations WHERE slug = :slug'),
            {'slug': slug},
        ).fetchall()
        if len(matches) == 1:
            org_id = matches[0][0]
            bind.execute(
                text(
                    f'UPDATE {table} SET organization_id = :org_id '
                    f'WHERE organization_id IS NULL AND company_key = :ck'
                ),
                {'org_id': org_id, 'ck': company_key},
            )
        # Zero or ambiguous (>1) matches: leave NULL — caught by the guard below.


def _assert_fully_backfilled(bind) -> None:
    problems = []
    for table in _TABLES:
        row = bind.execute(
            text(f'SELECT COUNT(*) FROM {table} WHERE organization_id IS NULL')
        ).fetchone()
        remaining = row[0] if row else 0
        if remaining:
            samples = bind.execute(
                text(
                    f'SELECT DISTINCT company_key FROM {table} '
                    f'WHERE organization_id IS NULL LIMIT 10'
                )
            ).fetchall()
            problems.append(
                f'{table}: {remaining} row(s) with unresolved organization_id '
                f'(sample company_key values: {[s[0] for s in samples]!r})'
            )
    if problems:
        raise RuntimeError(
            'BUG-004 migration aborted — cannot safely assign organization_id for:\n'
            + '\n'.join(problems)
            + '\nThese company_key values do not map to exactly one organizations.slug '
              '(zero or ambiguous matches). Resolve manually (merge/rename the orgs, or '
              'delete orphaned rows) and re-run the migration. Refusing to guess.'
        )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. oauth_tokens.hrid was queried/written by the app but never existed —
    #    add it now (nullable: legacy rows, if any, cannot be attributed to a
    #    recruiter after the fact).
    op.add_column('oauth_tokens', sa.Column('hrid', sa.String(length=20), nullable=True))
    op.create_foreign_key(
        'oauth_tokens_hrid_fkey', 'oauth_tokens', 'hr_signup',
        ['hrid'], ['hrid'], ondelete='CASCADE',
    )
    op.create_index('ix_oauth_tokens_hrid', 'oauth_tokens', ['hrid'])

    # 2. Backfill organization_id from company_key -> organizations.slug.
    for table in _TABLES:
        _backfill_organization_id(bind, table)

    # 3. Fail closed if anything is still ambiguous/unresolved.
    _assert_fully_backfilled(bind)

    # 4. organization_id becomes the authoritative, required tenant boundary.
    for table in _TABLES:
        op.alter_column(table, 'organization_id', existing_type=sa.Uuid(), nullable=False)

    # 5. Replace company_key-scoped uniqueness with organization_id-scoped
    #    uniqueness (hrid-scoped for oauth_tokens — tokens are per-recruiter).
    op.drop_constraint(
        'uq_integration_provider_company_provider', 'integration_provider', type_='unique'
    )
    op.create_unique_constraint(
        'uq_integration_provider_org_provider', 'integration_provider', ['organization_id', 'provider']
    )

    op.drop_constraint(
        'uq_external_applications_provider_app', 'external_applications', type_='unique'
    )
    op.create_unique_constraint(
        'uq_external_applications_org_provider_app',
        'external_applications',
        ['organization_id', 'provider', 'external_application_id'],
    )

    op.drop_constraint('uq_oauth_tokens_company_provider', 'oauth_tokens', type_='unique')
    op.create_unique_constraint(
        'uq_oauth_tokens_hrid_provider', 'oauth_tokens', ['hrid', 'provider']
    )


def downgrade() -> None:
    op.drop_constraint('uq_oauth_tokens_hrid_provider', 'oauth_tokens', type_='unique')
    op.create_unique_constraint(
        'uq_oauth_tokens_company_provider', 'oauth_tokens', ['company_key', 'provider']
    )

    op.drop_constraint(
        'uq_external_applications_org_provider_app', 'external_applications', type_='unique'
    )
    op.create_unique_constraint(
        'uq_external_applications_provider_app',
        'external_applications',
        ['company_key', 'provider', 'external_application_id'],
    )

    op.drop_constraint(
        'uq_integration_provider_org_provider', 'integration_provider', type_='unique'
    )
    op.create_unique_constraint(
        'uq_integration_provider_company_provider', 'integration_provider', ['company_key', 'provider']
    )

    for table in _TABLES:
        op.alter_column(table, 'organization_id', existing_type=sa.Uuid(), nullable=True)

    op.drop_index('ix_oauth_tokens_hrid', table_name='oauth_tokens')
    op.drop_constraint('oauth_tokens_hrid_fkey', 'oauth_tokens', type_='foreignkey')
    op.drop_column('oauth_tokens', 'hrid')
