-- =============================================================================
-- Sprint 1.3 — Remove legacy RBAC boolean columns and sync trigger
-- =============================================================================

DROP TRIGGER IF EXISTS trg_hr_signup_role_sync ON hr_signup;
DROP FUNCTION IF EXISTS hr_signup_role_sync();

ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_super_admin;
ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_head_hr;
ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_ceo;
