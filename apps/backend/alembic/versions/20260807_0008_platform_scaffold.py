"""Phase 5+future: platform scaffold — notifications, audit, jobs queue, pgvector opt-in.

Revision ID: 20260807_0008
Revises: 20260807_0007
Create Date: 2026-08-07

Creates future-ready tables without enabling RLS/partitioning yet.
pgvector extension is attempted; ignored if unavailable.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0008'
down_revision: Union[str, Sequence[str], None] = '20260807_0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Optional pgvector — must use SAVEPOINT so failure does not abort the migration txn
    conn = op.get_bind()
    conn.execute(text('SAVEPOINT sp_vector_ext'))
    try:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        conn.execute(text('RELEASE SAVEPOINT sp_vector_ext'))
    except Exception:
        conn.execute(text('ROLLBACK TO SAVEPOINT sp_vector_ext'))

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
            CREATE INDEX IF NOT EXISTS ix_notifications_recipient
            ON notifications (recipient_type, recipient_id, created_at DESC)
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_notifications_status_scheduled
            ON notifications (status, scheduled_at)
            WHERE status = 'pending'
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
            CREATE INDEX IF NOT EXISTS ix_audit_events_org_created
            ON audit_events (organization_id, created_at DESC)
            """
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_audit_events_entity
            ON audit_events (entity_type, entity_id, created_at DESC)
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
            CREATE INDEX IF NOT EXISTS ix_background_jobs_poll
            ON background_jobs (status, run_after)
            WHERE status IN ('queued', 'running')
            """
        )
    )

    # Embedding vector columns only if pgvector is present
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                    BEGIN
                        ALTER TABLE parsed_resumes
                            ADD COLUMN IF NOT EXISTS embedding vector(1536);
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;
                    BEGIN
                        ALTER TABLE parsed_jds
                            ADD COLUMN IF NOT EXISTS embedding vector(1536);
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;
                END IF;
            END $$
            """
        )
    )

    # Retention helper comment table (policy metadata)
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
    op.execute(
        text(
            """
            INSERT INTO data_retention_policies (table_name, retain_days, partition_hint, notes)
            VALUES
                ('login_history', 365, 'monthly', 'Auth attempt audit'),
                ('sync_logs', 90, 'monthly', 'Integration sync payloads'),
                ('webhook_events', 90, 'monthly', 'Inbound provider webhooks'),
                ('provider_events', 90, 'monthly', 'Outbound/internal provider events'),
                ('audit_events', 730, 'monthly', 'Security/compliance audit trail'),
                ('notifications', 180, 'monthly', 'Notification delivery log')
            ON CONFLICT (table_name) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(text('DROP TABLE IF EXISTS data_retention_policies'))
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
    op.execute(text('DROP TABLE IF EXISTS background_jobs'))
    op.execute(text('DROP TABLE IF EXISTS audit_events'))
    op.execute(text('DROP TABLE IF EXISTS notification_preferences'))
    op.execute(text('DROP TABLE IF EXISTS notifications'))
