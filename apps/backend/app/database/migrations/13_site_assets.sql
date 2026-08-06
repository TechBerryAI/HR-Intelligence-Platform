-- Public / product site assets stored in Postgres (e.g. landing hero video).
-- Serves durable media without depending on gitignored disk volumes alone.
CREATE TABLE IF NOT EXISTS site_assets (
    asset_key    VARCHAR(128) PRIMARY KEY,
    filename     VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    data         BYTEA NOT NULL,
    byte_size    BIGINT NOT NULL CHECK (byte_size >= 0),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_assets_updated_at
    ON site_assets (updated_at DESC);
