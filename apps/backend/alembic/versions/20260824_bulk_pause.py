"""Allow Paused status on bulk parse sessions.

Revision ID: 20260824_bulk_pause
Revises: 20260814_cid_pad3
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260824_bulk_pause'
down_revision: Union[str, Sequence[str], None] = '20260814_cid_pad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE bulk_parse_sessions DROP CONSTRAINT IF EXISTS bulk_parse_sessions_status_check')
    op.execute(
        """
        ALTER TABLE bulk_parse_sessions
        ADD CONSTRAINT bulk_parse_sessions_status_check
        CHECK (status IN ('Queued', 'Running', 'Completed', 'Failed', 'Cancelled', 'Paused'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE bulk_parse_sessions
        SET status = 'Cancelled'
        WHERE status = 'Paused'
        """
    )
    op.execute('ALTER TABLE bulk_parse_sessions DROP CONSTRAINT IF EXISTS bulk_parse_sessions_status_check')
    op.execute(
        """
        ALTER TABLE bulk_parse_sessions
        ADD CONSTRAINT bulk_parse_sessions_status_check
        CHECK (status IN ('Queued', 'Running', 'Completed', 'Failed', 'Cancelled'))
        """
    )
