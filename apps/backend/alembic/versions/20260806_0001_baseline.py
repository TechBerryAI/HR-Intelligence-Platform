"""Baseline + consolidated schema (schema_pg 01–04).

Revision ID: 20260806_0001
Revises:
Create Date: 2026-08-06

Applies the consolidated SQL under ``apps/backend/schema_pg/``:
  01_core.sql, 02_domain.sql, 03_integrations.sql, 04_seeds.sql

New schema changes: ``alembic revision -m "…"`` then edit upgrade().
"""
from typing import Sequence, Union

revision: str = '20260806_0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    from app.database.schema_apply import apply_consolidated_schema

    apply_consolidated_schema(op.get_bind())


def downgrade() -> None:
    # Full schema drop is intentionally unsupported.
    pass
