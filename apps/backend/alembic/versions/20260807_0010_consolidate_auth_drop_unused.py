"""Consolidate auth tables; drop unused offers/events tables.

Revision ID: 20260807_0010
Revises: 20260807_0009
Create Date: 2026-08-07

- Drop ``offers`` (unused scaffold)
- Fold ``provider_events`` / ``webhook_events`` into ``sync_logs``, then drop
- Drop ``hr_login`` (sessions read ``login_history`` instead)
- Fold ``HRAuth`` into ``hr_signup`` (account_status + otp columns), then drop
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260807_0010'
down_revision: Union[str, Sequence[str], None] = '20260807_0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- offers ---
    op.execute(text('DROP TABLE IF EXISTS offers CASCADE'))

    # --- provider_events → sync_logs ---
    op.execute(
        text(
            """
            INSERT INTO sync_logs (
                company_key, provider, operation, job_id,
                request_payload, status, created_at
            )
            SELECT
                COALESCE(company_key, 'unknown'),
                COALESCE(provider, 'system'),
                COALESCE(event_type, 'provider_event'),
                job_id,
                payload,
                COALESCE(status, 'dispatched'),
                created_at
            FROM provider_events
            """
        )
    )
    op.execute(text('DROP TABLE IF EXISTS provider_events CASCADE'))

    # --- webhook_events → sync_logs ---
    op.execute(
        text(
            """
            INSERT INTO sync_logs (
                company_key, provider, operation,
                request_payload, response_payload, status, created_at
            )
            SELECT
                COALESCE(company_key, 'unknown'),
                provider,
                COALESCE(event_type, 'webhook'),
                payload,
                headers_json,
                CASE WHEN processed THEN 'completed' ELSE 'pending' END,
                created_at
            FROM webhook_events
            """
        )
    )
    op.execute(text('DROP TABLE IF EXISTS webhook_events CASCADE'))

    # --- hr_login: optional historical copy, then drop ---
    op.execute(
        text(
            """
            INSERT INTO login_history (email, user_type, status, attempted_at, user_id)
            SELECT l.email, 'HR', 'success', l.logged_in_at, l.hrid
            FROM hr_login l
            WHERE NOT EXISTS (
                SELECT 1 FROM login_history h
                WHERE h.email = l.email
                  AND h.user_type = 'HR'
                  AND h.status = 'success'
                  AND h.user_id = l.hrid
                  AND h.attempted_at = l.logged_in_at
            )
            """
        )
    )
    op.execute(text('DROP TABLE IF EXISTS hr_login CASCADE'))

    # --- hr_signup: account_status + OTP (absorb HRAuth) ---
    op.execute(
        text(
            """
            ALTER TABLE hr_signup
            ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) NOT NULL DEFAULT 'active'
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'hr_signup_account_status_check'
                ) THEN
                    ALTER TABLE hr_signup
                    ADD CONSTRAINT hr_signup_account_status_check
                    CHECK (account_status IN ('pending', 'active'));
                END IF;
            END $$
            """
        )
    )
    op.execute(text('ALTER TABLE hr_signup ADD COLUMN IF NOT EXISTS otp VARCHAR(6) NULL'))
    op.execute(text('ALTER TABLE hr_signup ADD COLUMN IF NOT EXISTS otp_expiry TIMESTAMPTZ NULL'))
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_hr_signup_account_status
            ON hr_signup (account_status)
            """
        )
    )

    # Migrate unverified HRAuth rows into pending hr_signup
    op.execute(
        text(
            """
            INSERT INTO hr_signup (
                hrid, full_name, email, company, password, role,
                account_status, otp, otp_expiry, created_at, updated_at
            )
            SELECT
                'HRID' || LPAD((
                    COALESCE((
                        SELECT MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER))
                        FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$'
                    ), 0) + ROW_NUMBER() OVER (ORDER BY a.id)
                )::text, 3, '0'),
                a.full_name,
                a.email,
                a.company,
                a.password_hash,
                'RECRUITER',
                'pending',
                a.otp,
                a.otp_expiry,
                a.created_at,
                a.updated_at
            FROM "HRAuth" a
            WHERE COALESCE(a.is_verified, false) = false
              AND NOT EXISTS (
                  SELECT 1 FROM hr_signup s
                  WHERE LOWER(TRIM(s.email)) = LOWER(TRIM(a.email))
              )
            """
        )
    )
    # Copy in-flight OTP from verified HRAuth onto matching active signup (password-reset)
    op.execute(
        text(
            """
            UPDATE hr_signup s
            SET otp = a.otp,
                otp_expiry = a.otp_expiry
            FROM "HRAuth" a
            WHERE LOWER(TRIM(s.email)) = LOWER(TRIM(a.email))
              AND COALESCE(a.is_verified, false) = true
              AND a.otp IS NOT NULL
              AND s.otp IS NULL
            """
        )
    )
    op.execute(text('DROP TABLE IF EXISTS "HRAuth" CASCADE'))


def downgrade() -> None:
    # Recreate minimal dropped tables (data not restored)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS "HRAuth" (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                company VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                otp VARCHAR(6) NULL,
                otp_expiry TIMESTAMPTZ NULL,
                is_verified BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS hr_login (
                id SERIAL PRIMARY KEY,
                hrid VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid) ON DELETE CASCADE,
                email VARCHAR(255) NOT NULL,
                logged_in_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS provider_events (
                id SERIAL PRIMARY KEY,
                company_key VARCHAR(255) NULL,
                event_type VARCHAR(64) NOT NULL,
                job_id VARCHAR(64) NULL,
                provider VARCHAR(64) NULL,
                payload JSONB NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                id SERIAL PRIMARY KEY,
                company_key VARCHAR(255) NULL,
                provider VARCHAR(64) NOT NULL,
                event_type VARCHAR(64) NULL,
                payload JSONB NULL,
                headers_json JSONB NULL,
                processed BOOLEAN NOT NULL DEFAULT FALSE,
                error_message TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS offers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                generated_by VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
                status VARCHAR(30) NOT NULL DEFAULT 'Draft',
                compensation_json JSONB NULL,
                letter_toon TEXT NULL,
                sent_at TIMESTAMPTZ NULL,
                expires_at TIMESTAMPTZ NULL,
                responded_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(20) NULL REFERENCES hr_signup(hrid),
                updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid)
            )
            """
        )
    )
    # Keep account_status/otp columns on downgrade (non-destructive)
