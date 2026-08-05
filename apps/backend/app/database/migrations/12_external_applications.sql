-- External applications synced from custom HTTP job-board adapters
CREATE TABLE IF NOT EXISTS external_applications (
    id                      SERIAL PRIMARY KEY,
    company_key             VARCHAR(255) NOT NULL,
    provider                VARCHAR(64) NOT NULL,
    job_id                  VARCHAR(64) NULL,
    external_job_id         VARCHAR(128) NULL,
    external_application_id VARCHAR(128) NOT NULL,
    candidate_email         VARCHAR(255) NULL,
    candidate_name          VARCHAR(255) NULL,
    mapped_status           VARCHAR(64) NULL,
    payload                 JSONB NULL,
    last_synced_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_external_applications_provider_app
        UNIQUE (company_key, provider, external_application_id)
);

CREATE INDEX IF NOT EXISTS idx_external_applications_company
    ON external_applications (company_key, provider);
CREATE INDEX IF NOT EXISTS idx_external_applications_job
    ON external_applications (job_id);
