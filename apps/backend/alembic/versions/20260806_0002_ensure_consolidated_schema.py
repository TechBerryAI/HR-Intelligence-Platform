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
    """No-op for already-provisioned DBs.

    Re-applying the full consolidated schema_pg inside Alembic's transaction
    caused the entire upgrade chain to roll back (idempotent DDL + seeds).
    Fresh installs should run ``apply_consolidated_schema`` once via
    ``alembic upgrade 20260806_0001`` (baseline) or ``schema_apply`` manually,
    then stamp ``20260806_0002`` and continue with incremental revisions.
    """
    # Intentionally empty — see module docstring / alembic README.
    return


def downgrade() -> None:
    pass
