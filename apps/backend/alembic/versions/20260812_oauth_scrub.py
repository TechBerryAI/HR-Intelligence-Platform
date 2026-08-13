"""Scrub plaintext OAuth secrets from oauth_tokens.raw_json.

Revision ID: 20260812_oauth_scrub
Revises: 20260812_candidates_org
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = '20260812_oauth_scrub'
down_revision: Union[str, Sequence[str], None] = '20260812_candidates_org'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep only non-sensitive metadata keys in raw_json.
    op.execute(
        text(
            """
            UPDATE oauth_tokens
            SET raw_json = COALESCE(
                (
                    SELECT jsonb_object_agg(key, value)
                    FROM jsonb_each(COALESCE(raw_json, '{}'::jsonb)) AS t(key, value)
                    WHERE key IN ('token_type', 'scope', 'expires_in')
                ),
                '{}'::jsonb
            )
            WHERE raw_json IS NOT NULL
              AND (
                raw_json ? 'access_token'
                OR raw_json ? 'refresh_token'
                OR raw_json ? 'id_token'
                OR raw_json ? 'client_secret'
                OR raw_json ? 'authorization_code'
              )
            """
        )
    )


def downgrade() -> None:
    # Irreversible data scrub — secrets cannot be restored from encrypted columns into raw_json.
    pass
