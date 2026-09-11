"""Replace hr_signup email unique constraint with case-insensitive unique index.

Revision ID: 20260911_email_ci
Revises: 20260911_org_fk_restrict
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = '20260911_email_ci'
down_revision: Union[str, Sequence[str], None] = '20260911_org_fk_restrict'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dupes = conn.execute(
        text(
            """
            SELECT lower(trim(email)) AS norm, COUNT(*) AS cnt
            FROM hr_signup
            WHERE email IS NOT NULL AND trim(email) <> ''
            GROUP BY lower(trim(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dupes:
        samples = ', '.join(f'{r[0]}({r[1]})' for r in dupes[:5])
        raise RuntimeError(
            'Cannot create case-insensitive unique email index: '
            f'duplicate normalized emails exist: {samples}'
        )

    op.execute('ALTER TABLE hr_signup DROP CONSTRAINT IF EXISTS hr_signup_email_key')
    op.execute('DROP INDEX IF EXISTS hr_signup_email_key')
    op.execute(
        """
        CREATE UNIQUE INDEX ux_hr_signup_normalized_email
        ON hr_signup (lower(trim(email)))
        """
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ux_hr_signup_normalized_email')
    op.execute(
        """
        ALTER TABLE hr_signup
        ADD CONSTRAINT hr_signup_email_key UNIQUE (email)
        """
    )
