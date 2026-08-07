"""Rename candidate_signup → candidates; login_history HR-only.

Revision ID: 20260807_0011
Revises: 20260807_0010
Create Date: 2026-08-07

Applicants no longer have accounts — they apply from the jobs page.
``candidate_signup`` implied auth; rename to ``candidates``.
``login_history`` no longer needs a candidate user_type.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0011'
down_revision: Union[str, Sequence[str], None] = '20260807_0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename identity table (FKs follow the table OID automatically)
    op.execute(text('ALTER TABLE IF EXISTS candidate_signup RENAME TO candidates'))
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgname = 'trg_candidate_signup_updated_at'
                ) THEN
                    ALTER TRIGGER trg_candidate_signup_updated_at
                        ON candidates RENAME TO trg_candidates_updated_at;
                END IF;
            END $$
            """
        )
    )
    op.execute(
        text(
            """
            COMMENT ON TABLE candidates IS
              'Passwordless applicant identity (CID). Created on public job apply — not a login account.'
            """
        )
    )

    # login_history: drop obsolete candidate auth attempts, tighten CHECK
    op.execute(
        text("DELETE FROM login_history WHERE LOWER(user_type) = 'candidate'")
    )
    op.execute(text('ALTER TABLE login_history DROP CONSTRAINT IF EXISTS login_history_user_type_check'))
    op.execute(
        text(
            """
            ALTER TABLE login_history
            ADD CONSTRAINT login_history_user_type_check
            CHECK (user_type IN ('HR'))
            """
        )
    )


def downgrade() -> None:
    op.execute(text('ALTER TABLE login_history DROP CONSTRAINT IF EXISTS login_history_user_type_check'))
    op.execute(
        text(
            """
            ALTER TABLE login_history
            ADD CONSTRAINT login_history_user_type_check
            CHECK (user_type IN ('HR', 'candidate'))
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgname = 'trg_candidates_updated_at'
                ) THEN
                    ALTER TRIGGER trg_candidates_updated_at
                        ON candidates RENAME TO trg_candidate_signup_updated_at;
                END IF;
            END $$
            """
        )
    )
    op.execute(text('ALTER TABLE IF EXISTS candidates RENAME TO candidate_signup'))
