"""Phase 2: organizations table + organization_id FKs with backfill.

Revision ID: 20260807_0005
Revises: 20260807_0004
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0005'
down_revision: Union[str, Sequence[str], None] = '20260807_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_organizations_slug
            ON organizations (slug)
            """
        )
    )

    for table in (
        'hr_signup',
        'jobs',
        'integration_provider',
        'external_jobs',
        'external_applications',
        'sync_logs',
        'provider_events',
        'webhook_events',
        'oauth_tokens',
    ):
        op.execute(
            text(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS organization_id UUID NULL
                REFERENCES organizations(id) ON DELETE SET NULL
                """
            )
        )
        op.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS ix_{table}_organization_id
                ON {table} (organization_id)
                """
            )
        )

    # Backfill orgs from distinct company / company_key values
    op.execute(
        text(
            """
            INSERT INTO organizations (name, slug)
            SELECT name, slug FROM (
                SELECT DISTINCT ON (slug)
                    name,
                    slug
                FROM (
                SELECT
                    TRIM(company) AS name,
                    LOWER(REGEXP_REPLACE(
                        REGEXP_REPLACE(TRIM(LOWER(company)),
                            '\\s+(private limited|pvt\\.?\\s*ltd\\.?|ltd\\.?|inc\\.?|llc)\\s*$',
                            '', 'gi'),
                        '[^a-z0-9]+', '-', 'g'
                    )) AS slug
                FROM hr_signup
                WHERE company IS NOT NULL AND TRIM(company) <> ''
                UNION ALL
                SELECT
                    TRIM(company) AS name,
                    LOWER(REGEXP_REPLACE(
                        REGEXP_REPLACE(TRIM(LOWER(company)),
                            '\\s+(private limited|pvt\\.?\\s*ltd\\.?|ltd\\.?|inc\\.?|llc)\\s*$',
                            '', 'gi'),
                        '[^a-z0-9]+', '-', 'g'
                    )) AS slug
                FROM jobs
                WHERE company IS NOT NULL AND TRIM(company) <> ''
                UNION ALL
                SELECT
                    COALESCE(NULLIF(TRIM(company), ''), company_key) AS name,
                    LOWER(REGEXP_REPLACE(
                        TRIM(LOWER(company_key)),
                        '[^a-z0-9]+', '-', 'g'
                    )) AS slug
                FROM integration_provider
                WHERE company_key IS NOT NULL AND TRIM(company_key) <> ''
                ) raw
                WHERE slug IS NOT NULL AND slug <> '' AND slug <> '-'
                ORDER BY slug, name
            ) deduped
            ON CONFLICT (slug) DO NOTHING
            """
        )
    )

    op.execute(
        text(
            """
            UPDATE hr_signup h
            SET organization_id = o.id
            FROM organizations o
            WHERE h.organization_id IS NULL
              AND h.company IS NOT NULL
              AND o.slug = LOWER(REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(LOWER(h.company)),
                        '\\s+(private limited|pvt\\.?\\s*ltd\\.?|ltd\\.?|inc\\.?|llc)\\s*$',
                        '', 'gi'),
                    '[^a-z0-9]+', '-', 'g'
                  ))
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE jobs j
            SET organization_id = o.id
            FROM organizations o
            WHERE j.organization_id IS NULL
              AND j.company IS NOT NULL
              AND o.slug = LOWER(REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(LOWER(j.company)),
                        '\\s+(private limited|pvt\\.?\\s*ltd\\.?|ltd\\.?|inc\\.?|llc)\\s*$',
                        '', 'gi'),
                    '[^a-z0-9]+', '-', 'g'
                  ))
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE integration_provider ip
            SET organization_id = o.id
            FROM organizations o
            WHERE ip.organization_id IS NULL
              AND o.slug = LOWER(REGEXP_REPLACE(
                    TRIM(LOWER(ip.company_key)),
                    '[^a-z0-9]+', '-', 'g'
                  ))
            """
        )
    )
    for table in (
        'external_jobs',
        'external_applications',
        'sync_logs',
        'provider_events',
        'webhook_events',
        'oauth_tokens',
    ):
        op.execute(
            text(
                f"""
                UPDATE {table} t
                SET organization_id = o.id
                FROM organizations o
                WHERE t.organization_id IS NULL
                  AND t.company_key IS NOT NULL
                  AND o.slug = LOWER(REGEXP_REPLACE(
                        TRIM(LOWER(t.company_key)),
                        '[^a-z0-9]+', '-', 'g'
                      ))
                """
            )
        )


def downgrade() -> None:
    for table in (
        'oauth_tokens',
        'webhook_events',
        'provider_events',
        'sync_logs',
        'external_applications',
        'external_jobs',
        'integration_provider',
        'jobs',
        'hr_signup',
    ):
        op.execute(text(f'DROP INDEX IF EXISTS ix_{table}_organization_id'))
        op.execute(text(f'ALTER TABLE {table} DROP COLUMN IF EXISTS organization_id'))
    op.execute(text('DROP TABLE IF EXISTS organizations'))
