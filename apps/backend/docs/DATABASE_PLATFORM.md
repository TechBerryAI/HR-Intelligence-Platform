"""Future platform tables — **do not create empty**.

When a feature ships, add a focused Alembic revision for only what that
feature needs. Candidates (documented, not provisioned):

- `notifications` / `notification_preferences` — when in-app notification storage ships
- `audit_events` — when mutation audit trail ships
- `background_jobs` — when DB-backed job queue ships
- `data_retention_policies` — optional metadata for archival jobs

RLS / partitioning notes stay design-only until `organization_id` is enforced
in the app request path:

  ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
  CREATE POLICY jobs_org_isolation ON jobs
    USING (organization_id::text = current_setting('app.organization_id', true));

Partitioning candidates at high volume: `login_history`, `sync_logs`,
`webhook_events` — RANGE by `created_at` monthly.
"""
