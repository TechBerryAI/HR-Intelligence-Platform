"""Phase 3: blob offload columns — storage_backend, resume_raw_file_id, site_assets storage_url.

Revision ID: 20260807_0006
Revises: 20260807_0005
Create Date: 2026-08-07

Expand phase: new columns only. BYTEA columns kept nullable for migration window.
New writes prefer media storage (see parsing_storage / site_assets).
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0006'
down_revision: Union[str, Sequence[str], None] = '20260807_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        text(
            """
            ALTER TABLE raw_files
            ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32) NOT NULL DEFAULT 'postgres'
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE raw_files
            SET storage_backend = 'media'
            WHERE file_data IS NULL
              AND storage_url IS NOT NULL
              AND storage_url LIKE 'media:%'
            """
        )
    )
    op.execute(
        text(
            """
            ALTER TABLE candidate_profiles
            ADD COLUMN IF NOT EXISTS resume_raw_file_id UUID NULL
            REFERENCES raw_files(id) ON DELETE SET NULL
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_candidate_profiles_resume_raw_file
            ON candidate_profiles (resume_raw_file_id)
            """
        )
    )
    op.execute(
        text(
            """
            ALTER TABLE site_assets
            ADD COLUMN IF NOT EXISTS storage_url VARCHAR(1000) NULL
            """
        )
    )
    op.execute(
        text(
            """
            ALTER TABLE site_assets
            ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32) NOT NULL DEFAULT 'postgres'
            """
        )
    )
    # Allow empty BYTEA during offload (site_assets.data was NOT NULL)
    op.execute(text('ALTER TABLE site_assets ALTER COLUMN data DROP NOT NULL'))


def downgrade() -> None:
    op.execute(text('ALTER TABLE site_assets DROP COLUMN IF EXISTS storage_backend'))
    op.execute(text('ALTER TABLE site_assets DROP COLUMN IF EXISTS storage_url'))
    # Re-require data only if all rows have data
    op.execute(
        text(
            """
            UPDATE site_assets SET data = ''::bytea WHERE data IS NULL
            """
        )
    )
    op.execute(text('ALTER TABLE site_assets ALTER COLUMN data SET NOT NULL'))
    op.execute(text('DROP INDEX IF EXISTS ix_candidate_profiles_resume_raw_file'))
    op.execute(
        text('ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS resume_raw_file_id')
    )
    op.execute(text('ALTER TABLE raw_files DROP COLUMN IF EXISTS storage_backend'))
