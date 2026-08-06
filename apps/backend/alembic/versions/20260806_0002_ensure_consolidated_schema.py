"""Ensure consolidated schema is applied (for DBs stamped at empty baseline).

Revision ID: 20260806_0002
Revises: 20260806_0001
Create Date: 2026-08-06

Re-runs idempotent schema_pg apply so environments that stamped the empty
baseline still receive the consolidated schema.
"""
from typing import Sequence, Union

revision: str = '20260806_0002'
down_revision: Union[str, Sequence[str], None] = '20260806_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    from app.database.schema_apply import apply_consolidated_schema

    apply_consolidated_schema(op.get_bind())


def downgrade() -> None:
    pass
