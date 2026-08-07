"""Catalog integrity: site_assets.content_sha256 for media-volume verification.

Revision ID: 20260807_0012
Revises: 20260807_0011
Create Date: 2026-08-07

Postgres remains the catalog (hash, size, storage_url). Bytes live on MEDIA_ROOT.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0012'
down_revision: Union[str, Sequence[str], None] = '20260807_0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        text(
            """
            ALTER TABLE site_assets
            ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64) NULL
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_site_assets_content_sha256
            ON site_assets (content_sha256)
            WHERE content_sha256 IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(text('DROP INDEX IF EXISTS ix_site_assets_content_sha256'))
    op.execute(text('ALTER TABLE site_assets DROP COLUMN IF EXISTS content_sha256'))
