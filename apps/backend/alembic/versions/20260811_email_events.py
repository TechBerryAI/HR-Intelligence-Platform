"""application_email_events for candidate email send status

Revision ID: 20260811_email
Revises: 008763c9ff0f
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '20260811_email'
down_revision: Union[str, Sequence[str], None] = '008763c9ff0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table('application_email_events'):
        op.create_table(
            'application_email_events',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('application_id', sa.Integer(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
            sa.Column('email_kind', sa.String(64), nullable=False),
            sa.Column('recipient', sa.String(320), nullable=True),
            sa.Column('subject', sa.String(500), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='sent'),
            sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        )
    existing = {ix['name'] for ix in insp.get_indexes('application_email_events')}
    if 'ix_application_email_events_app_kind' not in existing:
        op.create_index(
            'ix_application_email_events_app_kind',
            'application_email_events',
            ['application_id', 'email_kind'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table('application_email_events'):
        existing = {ix['name'] for ix in insp.get_indexes('application_email_events')}
        if 'ix_application_email_events_app_kind' in existing:
            op.drop_index('ix_application_email_events_app_kind', table_name='application_email_events')
        op.drop_table('application_email_events')
