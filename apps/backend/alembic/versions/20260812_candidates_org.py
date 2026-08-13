"""Formalize candidates.organization_id + per-org email uniqueness (live DB already has these).

Revision ID: 20260812_candidates_org
Revises: 20260811_email
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = '20260812_candidates_org'
down_revision: Union[str, Sequence[str], None] = '20260811_email'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('candidates')}
    if 'organization_id' not in cols:
        op.add_column(
            'candidates',
            sa.Column('organization_id', sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            'candidates_organization_id_fkey',
            'candidates',
            'organizations',
            ['organization_id'],
            ['id'],
            ondelete='RESTRICT',
        )
        # Backfill from applications → jobs when possible
        bind.execute(
            text(
                """
                UPDATE candidates c
                SET organization_id = sub.org_id
                FROM (
                    SELECT a.candidate_id, MIN(j.organization_id::text)::uuid AS org_id
                    FROM applications a
                    JOIN jobs j ON j.jdid = a.job_id
                    WHERE j.organization_id IS NOT NULL
                    GROUP BY a.candidate_id
                ) sub
                WHERE c.cid = sub.candidate_id
                  AND c.organization_id IS NULL
                """
            )
        )

    indexes = {ix['name'] for ix in insp.get_indexes('candidates')}
    # Refresh after possible column add
    insp = inspect(bind)
    indexes = {ix['name'] for ix in insp.get_indexes('candidates')}
    if 'ix_candidates_organization_id' not in indexes:
        op.create_index(
            'ix_candidates_organization_id',
            'candidates',
            ['organization_id'],
        )
    if 'ux_candidates_org_normalized_email' not in indexes:
        bind.execute(
            text(
                """
                CREATE UNIQUE INDEX ux_candidates_org_normalized_email
                ON candidates (organization_id, lower(TRIM(BOTH FROM email)))
                WHERE organization_id IS NOT NULL
                """
            )
        )

    # Drop legacy global email unique if present
    cons = {
        c['name']
        for c in insp.get_unique_constraints('candidates')
    }
    if 'candidate_signup_email_key' in cons:
        op.drop_constraint('candidate_signup_email_key', 'candidates', type_='unique')


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = {ix['name'] for ix in insp.get_indexes('candidates')}
    if 'ux_candidates_org_normalized_email' in indexes:
        op.drop_index('ux_candidates_org_normalized_email', table_name='candidates')
    if 'ix_candidates_organization_id' in indexes:
        op.drop_index('ix_candidates_organization_id', table_name='candidates')
    cols = {c['name'] for c in insp.get_columns('candidates')}
    if 'organization_id' in cols:
        op.drop_constraint('candidates_organization_id_fkey', 'candidates', type_='foreignkey')
        op.drop_column('candidates', 'organization_id')
