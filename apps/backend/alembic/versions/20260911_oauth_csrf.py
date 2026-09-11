"""DB-backed OAuth CSRF state for multi-worker when Redis is unavailable.

Revision ID: 20260911_oauth_csrf
Revises: 20260824_bulk_pause
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260911_oauth_csrf'
down_revision: Union[str, Sequence[str], None] = '20260824_bulk_pause'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_csrf_state (
            state varchar(128) PRIMARY KEY,
            payload_json jsonb NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oauth_csrf_state_expires_at
        ON oauth_csrf_state (expires_at)
        """
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS oauth_csrf_state')
