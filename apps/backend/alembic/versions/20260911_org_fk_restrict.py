"""Change organizations FKs from ON DELETE SET NULL to ON DELETE RESTRICT.

Revision ID: 20260911_org_fk_restrict
Revises: 20260911_acct_deact
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260911_org_fk_restrict'
down_revision: Union[str, Sequence[str], None] = '20260911_acct_deact'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_SPECS = (
    ('external_applications', 'external_applications_organization_id_fkey'),
    ('external_jobs', 'external_jobs_organization_id_fkey'),
    ('hr_signup', 'hr_signup_organization_id_fkey'),
    ('integration_provider', 'integration_provider_organization_id_fkey'),
    ('jobs', 'jobs_organization_id_fkey'),
    ('oauth_tokens', 'oauth_tokens_organization_id_fkey'),
    ('sync_logs', 'sync_logs_organization_id_fkey'),
)


def upgrade() -> None:
    for table, fk_name in _FK_SPECS:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk_name}')
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE RESTRICT
            """
        )


def downgrade() -> None:
    for table, fk_name in _FK_SPECS:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk_name}')
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
            """
        )
