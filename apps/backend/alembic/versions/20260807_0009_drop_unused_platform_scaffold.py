"""Drop unused future-platform scaffold tables (lean schema).

Revision ID: 20260807_0009
Revises: 20260807_0008
Create Date: 2026-08-07

These were created empty for \"future readiness\" but nothing in the app
reads/writes them yet. Re-add via a real feature migration when needed.
Keeps ``organizations`` (in use for multi-tenancy).
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0009'
down_revision: Union[str, Sequence[str], None] = '20260807_0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text('DROP TABLE IF EXISTS data_retention_policies CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS background_jobs CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS audit_events CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS notification_preferences CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS notifications CASCADE'))
    # Optional embedding columns from 0008 (no-op if never created)
    op.execute(
        text(
            """
            DO $$
            BEGIN
                ALTER TABLE parsed_resumes DROP COLUMN IF EXISTS embedding;
                ALTER TABLE parsed_jds DROP COLUMN IF EXISTS embedding;
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END $$
            """
        )
    )


def downgrade() -> None:
    # Recreate minimal scaffold if someone downgrades (same shape as 0008)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NULL REFERENCES organizations(id) ON DELETE SET NULL,
                recipient_type VARCHAR(20) NOT NULL
                    CHECK (recipient_type IN ('hr', 'candidate', 'system')),
                recipient_id VARCHAR(50) NOT NULL,
                channel VARCHAR(20) NOT NULL DEFAULT 'email'
                    CHECK (channel IN ('email', 'in_app', 'webhook')),
                template_key VARCHAR(100) NULL,
                subject VARCHAR(500) NULL,
                body TEXT NULL,
                payload JSONB NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
                error_message TEXT NULL,
                scheduled_at TIMESTAMPTZ NULL,
                sent_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('hr', 'candidate')),
                user_id VARCHAR(50) NOT NULL,
                channel VARCHAR(20) NOT NULL DEFAULT 'email',
                event_key VARCHAR(100) NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_type, user_id, channel, event_key)
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NULL REFERENCES organizations(id) ON DELETE SET NULL,
                actor_type VARCHAR(20) NULL,
                actor_id VARCHAR(50) NULL,
                action VARCHAR(100) NOT NULL,
                entity_type VARCHAR(100) NULL,
                entity_id VARCHAR(100) NULL,
                metadata JSONB NULL,
                ip_address VARCHAR(100) NULL,
                user_agent VARCHAR(500) NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS background_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NULL REFERENCES organizations(id) ON DELETE SET NULL,
                job_type VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                payload JSONB NULL,
                result JSONB NULL,
                error_message TEXT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                started_at TIMESTAMPTZ NULL,
                completed_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS data_retention_policies (
                id SERIAL PRIMARY KEY,
                table_name VARCHAR(100) NOT NULL UNIQUE,
                retain_days INTEGER NOT NULL CHECK (retain_days > 0),
                partition_hint VARCHAR(50) NULL,
                notes TEXT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
