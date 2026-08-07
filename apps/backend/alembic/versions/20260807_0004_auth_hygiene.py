"""Phase 1: auth hygiene — hr_login password drop, login_history index, CID width, HRAuth index.

Revision ID: 20260807_0004
Revises: 20260807_0003
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0004'
down_revision: Union[str, Sequence[str], None] = '20260807_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text('ALTER TABLE hr_login DROP COLUMN IF EXISTS password'))
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_login_history_attempted_at
            ON login_history (attempted_at DESC)
            """
        )
    )
    # Widen CID formatting (CID00000001 …) — existing CIDs unchanged
    op.execute(
        text(
            """
            ALTER TABLE candidate_signup
            ALTER COLUMN cid SET DEFAULT (
                'CID' || LPAD(nextval('candidate_cid_seq')::text, 8, '0')
            )
            """
        )
    )
    # Duplicate unique index on HRAuth.email (keep HRAuth_email_key)
    op.execute(text('DROP INDEX IF EXISTS ix_hrauth_email'))
    op.execute(text('DROP INDEX IF EXISTS "IX_HRAuth_Email"'))


def downgrade() -> None:
    op.execute(
        text(
            """
            ALTER TABLE hr_login
            ADD COLUMN IF NOT EXISTS password VARCHAR(255) NOT NULL DEFAULT ''
            """
        )
    )
    op.execute(text('DROP INDEX IF EXISTS ix_login_history_attempted_at'))
    op.execute(
        text(
            """
            ALTER TABLE candidate_signup
            ALTER COLUMN cid SET DEFAULT (
                'CID' || LPAD(nextval('candidate_cid_seq')::text, 3, '0')
            )
            """
        )
    )
    op.execute(
        text(
            'CREATE UNIQUE INDEX IF NOT EXISTS ix_hrauth_email ON "HRAuth" (email)'
        )
    )
