"""Add durable outbox lease columns to external_jobs.

Revision ID: 20260812_ext_outbox
Revises: 20260812_bulk_leases
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '20260812_ext_outbox'
down_revision: Union[str, Sequence[str], None] = '20260812_bulk_leases'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('external_jobs')}

    if 'leased_by' not in cols:
        op.add_column('external_jobs', sa.Column('leased_by', sa.String(128), nullable=True))
    if 'leased_until' not in cols:
        op.add_column(
            'external_jobs',
            sa.Column('leased_until', sa.DateTime(timezone=True), nullable=True),
        )
    if 'next_attempt_at' not in cols:
        op.add_column(
            'external_jobs',
            sa.Column(
                'next_attempt_at',
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.text('NOW()'),
            ),
        )
    if 'pending_operation' not in cols:
        op.add_column(
            'external_jobs',
            sa.Column('pending_operation', sa.String(32), nullable=True),
        )

    # Refresh indexes after possible column adds
    insp = inspect(bind)
    indexes = {ix['name'] for ix in insp.get_indexes('external_jobs')}
    if 'ix_external_jobs_outbox_claim' not in indexes:
        op.create_index(
            'ix_external_jobs_outbox_claim',
            'external_jobs',
            ['sync_status', 'next_attempt_at', 'leased_until'],
        )

    # Backfill: any sticky pending rows become claimable immediately
    op.execute(
        sa.text(
            """
            UPDATE external_jobs
            SET next_attempt_at = COALESCE(next_attempt_at, NOW()),
                pending_operation = COALESCE(pending_operation, 'publish')
            WHERE sync_status = 'pending'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = {ix['name'] for ix in insp.get_indexes('external_jobs')}
    if 'ix_external_jobs_outbox_claim' in indexes:
        op.drop_index('ix_external_jobs_outbox_claim', table_name='external_jobs')
    cols = {c['name'] for c in insp.get_columns('external_jobs')}
    for col in ('pending_operation', 'next_attempt_at', 'leased_until', 'leased_by'):
        if col in cols:
            op.drop_column('external_jobs', col)
