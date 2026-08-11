"""describe_change

Revision ID: 008763c9ff0f
Revises: 20260810_s001
Create Date: 2026-08-10 06:37:20.749153
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008763c9ff0f'
down_revision: Union[str, Sequence[str], None] = '20260810_s001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
