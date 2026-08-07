"""Phase 0: interviews Invited status + applications status default.

Revision ID: 20260807_0003
Revises: 20260806_0002
Create Date: 2026-08-07

Fixes:
- interviews_status_check must allow 'Invited' (app insert path)
- applications.status default 'pending' violates CHECK → 'Applied'
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0003'
down_revision: Union[str, Sequence[str], None] = '20260806_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text('ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check'))
    op.execute(
        text(
            """
            ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
            CHECK (status IN (
                'Invited', 'Scheduled', 'InProgress',
                'Completed', 'Cancelled', 'Rescheduled'
            ))
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE applications
            SET status = 'Applied'
            WHERE status IS NULL OR LOWER(status) = 'pending'
            """
        )
    )
    op.execute(text("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'Applied'"))


def downgrade() -> None:
    op.execute(text('ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check'))
    op.execute(
        text(
            """
            ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
            CHECK (status IN (
                'Scheduled', 'InProgress', 'Completed', 'Cancelled', 'Rescheduled'
            ))
            """
        )
    )
    op.execute(text("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'pending'"))
