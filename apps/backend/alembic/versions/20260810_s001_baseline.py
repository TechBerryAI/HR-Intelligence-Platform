"""Squashed baseline schema (full HCIP Postgres schema at head).

Revision ID: 20260810_s001
Revises:
Create Date: 2026-08-10

Applies ``alembic/baseline/001_schema.sql`` + ``002_seeds.sql``.
Captured from the prior Alembic head ``20260810_0014`` (schema_pg + incremental
revisions). New schema changes: ``alembic revision -m "…"`` then edit upgrade().
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

revision: str = '20260810_s001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASELINE_DIR = Path(__file__).resolve().parents[1] / 'baseline'


def upgrade() -> None:
    from alembic import op
    from sqlalchemy import text

    from app.database.sql_apply import apply_sql_file

    bind = op.get_bind()
    # Ensure Alembic can resolve its version table after baseline DDL.
    bind.execute(text('SET search_path TO public'))
    schema = _BASELINE_DIR / '001_schema.sql'
    seeds = _BASELINE_DIR / '002_seeds.sql'
    if not schema.is_file():
        raise FileNotFoundError(schema)
    apply_sql_file(bind, schema, source='001_schema.sql')
    if seeds.is_file():
        apply_sql_file(bind, seeds, source='002_seeds.sql')
    bind.execute(text('SET search_path TO public'))


def downgrade() -> None:
    # Full schema drop is intentionally unsupported.
    pass
