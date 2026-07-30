-- -----------------------------------------------------------------------------
-- 08_public_apply_purge_candidate_auth.sql
-- Remove candidate login/auth tables; allow public resume uploads; drop passwords.
-- -----------------------------------------------------------------------------

-- 1) Drop candidate auth OTP / login tables
DROP TABLE IF EXISTS "CandidateAuth" CASCADE;
DROP TABLE IF EXISTS candidate_auth CASCADE;
DROP TABLE IF EXISTS candidate_login CASCADE;

-- 2) Drop password column from candidate_signup (passwordless applicants only)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'candidate_signup'
          AND column_name = 'password'
    ) THEN
        ALTER TABLE candidate_signup DROP COLUMN password;
    END IF;
END $$;

-- 3) Allow raw_files.uploader_role = 'public'
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'raw_files_uploader_role_check') THEN
        ALTER TABLE raw_files DROP CONSTRAINT raw_files_uploader_role_check;
    END IF;
    ALTER TABLE raw_files ADD CONSTRAINT raw_files_uploader_role_check
        CHECK (uploader_role IN ('candidate', 'admin', 'recruiter', 'public'));
END $$;
