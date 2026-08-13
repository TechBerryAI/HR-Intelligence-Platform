"""Add lease columns for multi-worker-safe bulk parse claiming.

Revision ID: 20260812_bulk_leases
Revises: 20260812_oauth_scrub
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '20260812_bulk_leases'
down_revision: Union[str, Sequence[str], None] = '20260812_oauth_scrub'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    file_cols = {c['name'] for c in insp.get_columns('bulk_parse_files')}
    if 'leased_by' not in file_cols:
        op.add_column('bulk_parse_files', sa.Column('leased_by', sa.String(128), nullable=True))
    if 'leased_until' not in file_cols:
        op.add_column(
            'bulk_parse_files',
            sa.Column('leased_until', sa.DateTime(timezone=True), nullable=True),
        )

    sess_cols = {c['name'] for c in insp.get_columns('bulk_parse_sessions')}
    if 'leased_by' not in sess_cols:
        op.add_column('bulk_parse_sessions', sa.Column('leased_by', sa.String(128), nullable=True))
    if 'leased_until' not in sess_cols:
        op.add_column(
            'bulk_parse_sessions',
            sa.Column('leased_until', sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {ix['name'] for ix in insp.get_indexes('bulk_parse_files')}
    if 'ix_bulk_parse_files_lease' not in indexes:
        op.create_index(
            'ix_bulk_parse_files_lease',
            'bulk_parse_files',
            ['status', 'leased_until'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = {ix['name'] for ix in insp.get_indexes('bulk_parse_files')}
    if 'ix_bulk_parse_files_lease' in indexes:
        op.drop_index('ix_bulk_parse_files_lease', table_name='bulk_parse_files')
    file_cols = {c['name'] for c in insp.get_columns('bulk_parse_files')}
    if 'leased_until' in file_cols:
        op.drop_column('bulk_parse_files', 'leased_until')
    if 'leased_by' in file_cols:
        op.drop_column('bulk_parse_files', 'leased_by')
    sess_cols = {c['name'] for c in insp.get_columns('bulk_parse_sessions')}
    if 'leased_until' in sess_cols:
        op.drop_column('bulk_parse_sessions', 'leased_until')
    if 'leased_by' in sess_cols:
        op.drop_column('bulk_parse_sessions', 'leased_by')
