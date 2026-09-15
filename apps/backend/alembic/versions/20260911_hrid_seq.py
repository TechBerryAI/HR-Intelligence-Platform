"""Allocate HRID values from a Postgres sequence (collision-safe).

Revision ID: 20260911_hrid_seq
Revises: 20260911_email_ci
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260911_hrid_seq'
down_revision: Union[str, Sequence[str], None] = '20260911_email_ci'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SEQUENCE IF NOT EXISTS hr_signup_hrid_seq')
    op.execute(
        """
        SELECT setval(
            'hr_signup_hrid_seq',
            GREATEST(
                1,
                COALESCE(
                    (SELECT MAX(CAST(SUBSTRING(hrid FROM 5) AS INT))
                     FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$'),
                    0
                )
            )
        )
        """
    )


def downgrade() -> None:
    op.execute('DROP SEQUENCE IF EXISTS hr_signup_hrid_seq')
