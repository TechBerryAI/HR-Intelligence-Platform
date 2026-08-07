"""Phase 1: auth hygiene — hr_login password drop, login_history index, CID width, HRAuth index.

Revision ID: 20260807_0004
Revises: 20260807_0003
Create Date: 2026-08-07

All steps are guarded: DBs that never had ``hr_login`` (or already dropped it)
must still advance this revision cleanly.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0004'
down_revision: Union[str, Sequence[str], None] = '20260807_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DROP COLUMN IF EXISTS only skips a missing *column* — not a missing *table*.
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.hr_login') IS NOT NULL THEN
                    ALTER TABLE hr_login DROP COLUMN IF EXISTS password;
                END IF;
            END $$
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.login_history') IS NOT NULL THEN
                    CREATE INDEX IF NOT EXISTS ix_login_history_attempted_at
                        ON login_history (attempted_at DESC);
                END IF;
            END $$
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.candidate_signup') IS NOT NULL
                   AND to_regclass('public.candidate_signup_cid_seq') IS NOT NULL THEN
                    ALTER TABLE candidate_signup
                        ALTER COLUMN cid
                        SET DEFAULT ('CID' || lpad(
                            nextval('candidate_signup_cid_seq')::text, 5, '0'
                        ));
                END IF;
            END $$
            """
        )
    )
    op.execute(text('DROP INDEX IF EXISTS ix_hrauth_email'))
    op.execute(text('DROP INDEX IF EXISTS "IX_HRAuth_Email"'))
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public."HRAuth"') IS NOT NULL THEN
                    CREATE UNIQUE INDEX IF NOT EXISTS "IX_HRAuth_Email"
                        ON "HRAuth" (email);
                END IF;
            END $$
            """
        )
    )


def downgrade() -> None:
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.hr_login') IS NOT NULL THEN
                    ALTER TABLE hr_login
                        ADD COLUMN IF NOT EXISTS password TEXT;
                END IF;
            END $$
            """
        )
    )
    op.execute(text('DROP INDEX IF EXISTS ix_login_history_attempted_at'))
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public.candidate_signup') IS NOT NULL
                   AND to_regclass('public.candidate_signup_cid_seq') IS NOT NULL THEN
                    ALTER TABLE candidate_signup
                        ALTER COLUMN cid
                        SET DEFAULT ('CID' || lpad(
                            nextval('candidate_signup_cid_seq')::text, 3, '0'
                        ));
                END IF;
            END $$
            """
        )
    )
    op.execute(text('DROP INDEX IF EXISTS "IX_HRAuth_Email"'))
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF to_regclass('public."HRAuth"') IS NOT NULL THEN
                    CREATE INDEX IF NOT EXISTS ix_hrauth_email ON "HRAuth" (email);
                END IF;
            END $$
            """
        )
    )
