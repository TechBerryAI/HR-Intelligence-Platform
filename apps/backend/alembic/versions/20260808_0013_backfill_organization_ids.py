"""Backfill organization_id on hr_signup and jobs from company names.

Revision ID: 20260808_0013
Revises: 20260807_0012
Create Date: 2026-08-08

Ensures every staff user and job is attached to an organizations row so
company-scoped access control can fail closed.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260808_0013'
down_revision: Union[str, Sequence[str], None] = '20260807_0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Insert missing orgs from distinct hr_signup.company / jobs.company values
    op.execute(
        text(
            """
            INSERT INTO organizations (name, slug)
            SELECT DISTINCT ON (slug) name, slug
            FROM (
                SELECT
                    trim(company) AS name,
                    trim(both '-' from lower(regexp_replace(
                        regexp_replace(lower(trim(company)),
                          '( private limited| pvt\\. ltd\\.| pvt ltd\\.| pvt\\. ltd| pvt ltd| ltd\\.| ltd| inc\\.| inc| llc)$',
                          '', 'i'),
                        '[^a-z0-9]+', '-', 'g'))) AS slug
                FROM hr_signup
                WHERE company IS NOT NULL AND length(trim(company)) > 0
                UNION ALL
                SELECT
                    trim(company) AS name,
                    trim(both '-' from lower(regexp_replace(
                        regexp_replace(lower(trim(company)),
                          '( private limited| pvt\\. ltd\\.| pvt ltd\\.| pvt\\. ltd| pvt ltd| ltd\\.| ltd| inc\\.| inc| llc)$',
                          '', 'i'),
                        '[^a-z0-9]+', '-', 'g'))) AS slug
                FROM jobs
                WHERE company IS NOT NULL AND length(trim(company)) > 0
            ) s
            WHERE slug IS NOT NULL AND slug <> ''
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
              AND length(trim(h.company)) > 0
              AND o.slug = trim(both '-' from lower(regexp_replace(
                    regexp_replace(lower(trim(h.company)),
                      '( private limited| pvt\\. ltd\\.| pvt ltd\\.| pvt\\. ltd| pvt ltd| ltd\\.| ltd| inc\\.| inc| llc)$',
                      '', 'i'),
                    '[^a-z0-9]+', '-', 'g')))
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
              AND length(trim(j.company)) > 0
              AND o.slug = trim(both '-' from lower(regexp_replace(
                    regexp_replace(lower(trim(j.company)),
                      '( private limited| pvt\\. ltd\\.| pvt ltd\\.| pvt\\. ltd| pvt ltd| ltd\\.| ltd| inc\\.| inc| llc)$',
                      '', 'i'),
                    '[^a-z0-9]+', '-', 'g')))
            """
        )
    )

    # Jobs still missing org: inherit from poster's organization_id
    op.execute(
        text(
            """
            UPDATE jobs j
            SET organization_id = h.organization_id
            FROM hr_signup h
            WHERE j.organization_id IS NULL
              AND j.posted_by = h.hrid
              AND h.organization_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    # Data backfill only — nothing to reverse safely
    pass
