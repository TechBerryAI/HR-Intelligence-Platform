-- Job-board Integration Framework (provider-agnostic, company-scoped)
-- Current: credentials + staging publish IDs. Schema stable for live provider APIs later.

CREATE TABLE IF NOT EXISTS integration_provider (
    id              SERIAL PRIMARY KEY,
    company_key     VARCHAR(255) NOT NULL,
    company         VARCHAR(255) NULL,
    provider        VARCHAR(64) NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    status          VARCHAR(32) NOT NULL DEFAULT 'disconnected',
    auth_type       VARCHAR(32) NOT NULL DEFAULT 'api_key',
    auto_publish    BOOLEAN NOT NULL DEFAULT FALSE,
    auto_sync       BOOLEAN NOT NULL DEFAULT FALSE,
    client_id       TEXT NULL,
    client_secret   TEXT NULL,
    access_token    TEXT NULL,
    refresh_token   TEXT NULL,
    expires_at      TIMESTAMPTZ NULL,
    settings_json   JSONB NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_integration_provider_company_provider UNIQUE (company_key, provider)
);

CREATE INDEX IF NOT EXISTS idx_integration_provider_company
    ON integration_provider (company_key);

CREATE TABLE IF NOT EXISTS external_jobs (
    id                  SERIAL PRIMARY KEY,
    company_key         VARCHAR(255) NOT NULL,
    job_id              VARCHAR(64) NOT NULL,
    provider            VARCHAR(64) NOT NULL,
    external_job_id     VARCHAR(128) NULL,
    external_status     VARCHAR(64) NULL,
    published_at        TIMESTAMPTZ NULL,
    last_sync           TIMESTAMPTZ NULL,
    sync_status         VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_message       TEXT NULL,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    request_payload     JSONB NULL,
    response_payload    JSONB NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_external_jobs_job_provider UNIQUE (job_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_external_jobs_company
    ON external_jobs (company_key);
CREATE INDEX IF NOT EXISTS idx_external_jobs_sync_status
    ON external_jobs (sync_status);
CREATE INDEX IF NOT EXISTS idx_external_jobs_provider
    ON external_jobs (provider);

CREATE TABLE IF NOT EXISTS sync_logs (
    id                  SERIAL PRIMARY KEY,
    company_key         VARCHAR(255) NOT NULL,
    provider            VARCHAR(64) NOT NULL,
    operation           VARCHAR(64) NOT NULL,
    job_id              VARCHAR(64) NULL,
    external_job_id     VARCHAR(128) NULL,
    request_payload     JSONB NULL,
    response_payload    JSONB NULL,
    status              VARCHAR(32) NOT NULL,
    execution_time_ms   INTEGER NULL,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_company_created
    ON sync_logs (company_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_logs_provider
    ON sync_logs (provider);

CREATE TABLE IF NOT EXISTS provider_events (
    id              SERIAL PRIMARY KEY,
    company_key     VARCHAR(255) NULL,
    event_type      VARCHAR(64) NOT NULL,
    job_id          VARCHAR(64) NULL,
    provider        VARCHAR(64) NULL,
    payload         JSONB NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provider_events_created
    ON provider_events (created_at DESC);

CREATE TABLE IF NOT EXISTS webhook_events (
    id              SERIAL PRIMARY KEY,
    company_key     VARCHAR(255) NULL,
    provider        VARCHAR(64) NOT NULL,
    event_type      VARCHAR(64) NULL,
    payload         JSONB NULL,
    headers_json    JSONB NULL,
    processed       BOOLEAN NOT NULL DEFAULT FALSE,
    error_message   TEXT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_provider
    ON webhook_events (provider, created_at DESC);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id              SERIAL PRIMARY KEY,
    company_key     VARCHAR(255) NOT NULL,
    provider        VARCHAR(64) NOT NULL,
    access_token    TEXT NULL,
    refresh_token   TEXT NULL,
    token_type      VARCHAR(32) NULL,
    scope           TEXT NULL,
    expires_at      TIMESTAMPTZ NULL,
    raw_json        JSONB NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_oauth_tokens_company_provider UNIQUE (company_key, provider)
);
