"""Phase 4: matches latest uniqueness, drop dead saved_jobs, ATS read path prep.

Revision ID: 20260807_0007
Revises: 20260807_0006
Create Date: 2026-08-07

Keeps applications ATS columns (contract later). Adds unique partial index so
is_latest is enforceable. Drops unused saved_jobs table.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0007'
down_revision: Union[str, Sequence[str], None] = '20260807_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure at most one is_latest per candidate+job before unique index
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY candidate_id, job_id
                           ORDER BY created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM matches
                WHERE is_latest = true
            )
            UPDATE matches m
            SET is_latest = false
            FROM ranked r
            WHERE m.id = r.id AND r.rn > 1
            """
        )
    )
    op.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_matches_latest
            ON matches (candidate_id, job_id)
            WHERE is_latest
            """
        )
    )
    op.execute(text('DROP TABLE IF EXISTS saved_jobs CASCADE'))


def downgrade() -> None:
    op.execute(text('DROP INDEX IF EXISTS ux_matches_latest'))
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS saved_jobs (
                id SERIAL PRIMARY KEY,
                candidate_id VARCHAR(20) NOT NULL
                    REFERENCES candidate_signup(cid) ON DELETE CASCADE,
                job_id VARCHAR(20) NOT NULL
                    REFERENCES jobs(jdid) ON DELETE CASCADE,
                saved_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (candidate_id, job_id)
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS IX_saved_jobs_candidate
            ON saved_jobs (candidate_id, saved_at DESC)
            """
        )
    )
