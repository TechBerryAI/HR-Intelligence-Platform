"""Allow hr_signup.account_status = deactivated (soft admin removal).

Revision ID: 20260911_acct_deact
Revises: 20260911_oauth_csrf
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260911_acct_deact'
down_revision: Union[str, Sequence[str], None] = '20260911_oauth_csrf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE hr_signup DROP CONSTRAINT IF EXISTS hr_signup_account_status_check')
    op.execute(
        """
        ALTER TABLE hr_signup
        ADD CONSTRAINT hr_signup_account_status_check
        CHECK (account_status::text = ANY (ARRAY[
            'pending'::character varying,
            'active'::character varying,
            'deactivated'::character varying
        ]::text[]))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE hr_signup
        SET account_status = 'pending'
        WHERE account_status = 'deactivated'
        """
    )
    op.execute('ALTER TABLE hr_signup DROP CONSTRAINT IF EXISTS hr_signup_account_status_check')
    op.execute(
        """
        ALTER TABLE hr_signup
        ADD CONSTRAINT hr_signup_account_status_check
        CHECK (account_status::text = ANY (ARRAY[
            'pending'::character varying,
            'active'::character varying
        ]::text[]))
        """
    )
