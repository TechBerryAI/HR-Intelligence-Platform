-- =============================================================================
-- 02_domain.sql — consolidated from: 04_domain_freeze.sql, 05_remove_legacy_rbac.sql, 08_public_apply_purge_candidate_auth.sql, 09_interview_ai_scheduling.sql, 10_jobs_keywords.sql, 14_interview_scheduling.sql, 15_raw_files_blob.sql
-- =============================================================================


-- >>> BEGIN 04_domain_freeze.sql
-- =============================================================================
-- Sprint 1.2 — Domain Freeze Migration (idempotent)
-- Central RBAC role, ownership, status enums, audit columns, new core tables.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Shared trigger: set updated_at on row update
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. hr_signup — central role + audit
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'role'
    ) THEN
        ALTER TABLE hr_signup ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'RECRUITER';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE hr_signup ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'updated_by'
    ) THEN
        ALTER TABLE hr_signup ADD COLUMN updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid);
    END IF;
END $$;

UPDATE hr_signup SET role = 'RECRUITER' WHERE role IS NULL;

-- Role CHECK constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hr_signup_role_check'
    ) THEN
        ALTER TABLE hr_signup ADD CONSTRAINT hr_signup_role_check
            CHECK (role IN ('CEO', 'HEAD_HR', 'RECRUITER'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS IX_hr_signup_role ON hr_signup(role);

DROP TRIGGER IF EXISTS trg_hr_signup_updated_at ON hr_signup;
CREATE TRIGGER trg_hr_signup_updated_at
    BEFORE UPDATE ON hr_signup
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 2. candidate_signup — audit
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_signup' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE candidate_signup ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_candidate_signup_updated_at ON candidate_signup;
CREATE TRIGGER trg_candidate_signup_updated_at
    BEFORE UPDATE ON candidate_signup
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 3. candidate_profiles — audit
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_profiles' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE candidate_profiles ADD COLUMN created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_profiles' AND column_name = 'created_by'
    ) THEN
        ALTER TABLE candidate_profiles ADD COLUMN created_by VARCHAR(20) NULL REFERENCES candidate_signup(cid);
    END IF;
END $$;

UPDATE candidate_profiles SET created_by = candidate_id WHERE created_by IS NULL;

-- -----------------------------------------------------------------------------
-- 4. jobs — status, ownership, audit, parsed_jd link
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'jobs' AND column_name = 'status'
    ) THEN
        ALTER TABLE jobs ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'Draft';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'jobs' AND column_name = 'created_by'
    ) THEN
        ALTER TABLE jobs ADD COLUMN created_by VARCHAR(20) NULL REFERENCES hr_signup(hrid);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'jobs' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE jobs ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'jobs' AND column_name = 'updated_by'
    ) THEN
        ALTER TABLE jobs ADD COLUMN updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'jobs' AND column_name = 'parsed_jd_id'
    ) THEN
        ALTER TABLE jobs ADD COLUMN parsed_jd_id UUID NULL;
    END IF;
END $$;

UPDATE jobs SET created_by = posted_by WHERE created_by IS NULL AND posted_by IS NOT NULL;
UPDATE jobs SET status = 'Published' WHERE (enabled = true OR enabled IS NULL) AND status = 'Draft';
UPDATE jobs SET status = 'Paused' WHERE enabled = false AND status IN ('Draft', 'Published');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'jobs_status_check') THEN
        ALTER TABLE jobs ADD CONSTRAINT jobs_status_check
            CHECK (status IN ('Draft', 'Published', 'Paused', 'Closed', 'Archived', 'Expired'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS IX_jobs_status_posted ON jobs(status, posted_on DESC);
CREATE INDEX IF NOT EXISTS IX_jobs_created_by_status ON jobs(created_by, status);

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- Sync enabled <-> status during transition
CREATE OR REPLACE FUNCTION jobs_status_enabled_sync()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        NEW.enabled := (NEW.status = 'Published');
    ELSIF NEW.enabled IS DISTINCT FROM OLD.enabled THEN
        IF NEW.enabled THEN
            NEW.status := 'Published';
        ELSIF NEW.status = 'Published' THEN
            NEW.status := 'Paused';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_status_enabled_sync ON jobs;
CREATE TRIGGER trg_jobs_status_enabled_sync
    BEFORE INSERT OR UPDATE ON jobs
    FOR EACH ROW EXECUTE PROCEDURE jobs_status_enabled_sync();

-- -----------------------------------------------------------------------------
-- 5. matches — new table (before applications.latest_match_id FK)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid),
    job_id VARCHAR(20) NOT NULL REFERENCES jobs(jdid),
    parsed_resume_id UUID NULL REFERENCES parsed_resumes(id) ON DELETE SET NULL,
    parsed_jd_id UUID NULL REFERENCES parsed_jds(id) ON DELETE SET NULL,
    match_score FLOAT NULL,
    matching_percentage FLOAT NULL,
    semantic_score FLOAT NULL,
    match_type VARCHAR(20) NOT NULL DEFAULT 'ats'
        CHECK (match_type IN ('rules', 'ats', 'semantic')),
    rationale TEXT NULL,
    analysis_toon TEXT NULL,
    model_version VARCHAR(100) NULL,
    is_latest BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL
);

CREATE INDEX IF NOT EXISTS IX_matches_candidate_job_latest ON matches(candidate_id, job_id, is_latest);
CREATE INDEX IF NOT EXISTS IX_matches_job_score ON matches(job_id, match_score DESC NULLS LAST);

-- -----------------------------------------------------------------------------
-- 6. applications — normalize status, match FK, audit
-- -----------------------------------------------------------------------------
-- Normalize legacy status values before CHECK
UPDATE applications SET status = 'Applied' WHERE LOWER(status) IN ('pending', 'applied');
UPDATE applications SET status = 'Screening' WHERE LOWER(status) = 'profile_viewed';
UPDATE applications SET status = 'Shortlisted' WHERE LOWER(status) = 'shortlisted';
UPDATE applications SET status = 'Rejected' WHERE LOWER(status) = 'rejected';
UPDATE applications SET status = 'Applied'
WHERE status NOT IN (
    'Applied', 'Screening', 'Matched', 'Shortlisted',
    'Interview', 'Rejected', 'Offer', 'Hired', 'Withdrawn'
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'applications' AND column_name = 'latest_match_id'
    ) THEN
        ALTER TABLE applications ADD COLUMN latest_match_id UUID NULL REFERENCES matches(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'applications' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE applications ADD COLUMN created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'applications' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE applications ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'applications' AND column_name = 'updated_by'
    ) THEN
        ALTER TABLE applications ADD COLUMN updated_by VARCHAR(20) NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'applications' AND column_name = 'created_by'
    ) THEN
        ALTER TABLE applications ADD COLUMN created_by VARCHAR(20) NULL REFERENCES candidate_signup(cid);
    END IF;
END $$;

UPDATE applications SET created_at = applied_at WHERE created_at IS NULL;
UPDATE applications SET created_by = candidate_id WHERE created_by IS NULL;

-- Backfill matches from applications with ATS data
INSERT INTO matches (
    candidate_id, job_id, match_score, matching_percentage, match_type,
    rationale, analysis_toon, is_latest, created_at, created_by
)
SELECT
    a.candidate_id, a.job_id, a.match_score, a.matching_percentage, 'ats',
    a.ats_reasoning, a.ats_analysis, true, COALESCE(a.applied_at, CURRENT_TIMESTAMP), a.candidate_id
FROM applications a
WHERE (a.match_score IS NOT NULL OR a.ats_reasoning IS NOT NULL OR a.ats_analysis IS NOT NULL)
  AND NOT EXISTS (
      SELECT 1 FROM matches m
      WHERE m.candidate_id = a.candidate_id AND m.job_id = a.job_id AND m.is_latest = true
  );

UPDATE applications a
SET latest_match_id = m.id
FROM matches m
WHERE m.candidate_id = a.candidate_id AND m.job_id = a.job_id AND m.is_latest = true
  AND a.latest_match_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'applications_status_check') THEN
        ALTER TABLE applications ADD CONSTRAINT applications_status_check
            CHECK (status IN (
                'Applied', 'Screening', 'Matched', 'Shortlisted',
                'Interview', 'Rejected', 'Offer', 'Hired', 'Withdrawn'
            ));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS IX_applications_job_status ON applications(job_id, status);
CREATE INDEX IF NOT EXISTS IX_applications_candidate_status ON applications(candidate_id, status);
CREATE INDEX IF NOT EXISTS IX_applications_latest_match ON applications(latest_match_id);

DROP TRIGGER IF EXISTS trg_applications_updated_at ON applications;
CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 7. bulk_parse_sessions + bulk_parse_files
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bulk_parse_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
    status VARCHAR(20) NOT NULL DEFAULT 'Queued'
        CHECK (status IN ('Queued', 'Running', 'Completed', 'Failed', 'Cancelled')),
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    total_files INTEGER NOT NULL DEFAULT 0,
    successful_files INTEGER NOT NULL DEFAULT 0,
    failed_files INTEGER NOT NULL DEFAULT 0,
    processing_time_ms BIGINT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_summary TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid)
);

CREATE INDEX IF NOT EXISTS IX_bulk_parse_sessions_owner ON bulk_parse_sessions(created_by, status, created_at DESC);

CREATE TABLE IF NOT EXISTS bulk_parse_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES bulk_parse_sessions(id) ON DELETE CASCADE,
    raw_file_id UUID NULL REFERENCES raw_files(id) ON DELETE SET NULL,
    parsed_resume_id UUID NULL REFERENCES parsed_resumes(id) ON DELETE SET NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Queued'
        CHECK (status IN ('Queued', 'Running', 'Completed', 'Failed', 'Cancelled')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    processing_time_ms BIGINT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS IX_bulk_parse_files_session_status ON bulk_parse_files(session_id, status);

DROP TRIGGER IF EXISTS trg_bulk_parse_sessions_updated_at ON bulk_parse_sessions;
CREATE TRIGGER trg_bulk_parse_sessions_updated_at
    BEFORE UPDATE ON bulk_parse_sessions
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_bulk_parse_files_updated_at ON bulk_parse_files;
CREATE TRIGGER trg_bulk_parse_files_updated_at
    BEFORE UPDATE ON bulk_parse_files
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 8. raw_files, parsed_resumes, parsed_jds — AI readiness + bulk link
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'raw_files' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE raw_files ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'raw_files' AND column_name = 'bulk_session_id'
    ) THEN
        ALTER TABLE raw_files ADD COLUMN bulk_session_id UUID NULL REFERENCES bulk_parse_sessions(id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_resumes' AND column_name = 'bulk_session_id'
    ) THEN
        ALTER TABLE parsed_resumes ADD COLUMN bulk_session_id UUID NULL REFERENCES bulk_parse_sessions(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_resumes' AND column_name = 'parse_status'
    ) THEN
        ALTER TABLE parsed_resumes ADD COLUMN parse_status VARCHAR(20) NOT NULL DEFAULT 'Parsed'
            CHECK (parse_status IN ('Text Extracted', 'Parsed', 'Parse Failed'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_resumes' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE parsed_resumes ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_resumes' AND column_name = 'embedding_metadata'
    ) THEN
        ALTER TABLE parsed_resumes ADD COLUMN embedding_metadata JSONB NULL;
    END IF;
END $$;

UPDATE parsed_resumes SET parse_status = 'Parsed' WHERE parse_status IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_jds' AND column_name = 'parse_status'
    ) THEN
        ALTER TABLE parsed_jds ADD COLUMN parse_status VARCHAR(20) NOT NULL DEFAULT 'Parsed'
            CHECK (parse_status IN ('Text Extracted', 'Parsed', 'Parse Failed'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_jds' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE parsed_jds ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'parsed_jds' AND column_name = 'embedding_metadata'
    ) THEN
        ALTER TABLE parsed_jds ADD COLUMN embedding_metadata JSONB NULL;
    END IF;
END $$;

UPDATE parsed_jds SET parse_status = 'Parsed' WHERE parse_status IS NULL;

-- jobs.parsed_jd_id FK (after parsed_jds exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'jobs_parsed_jd_id_fkey') THEN
        ALTER TABLE jobs ADD CONSTRAINT jobs_parsed_jd_id_fkey
            FOREIGN KEY (parsed_jd_id) REFERENCES parsed_jds(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS IX_parsed_resumes_bulk_session ON parsed_resumes(bulk_session_id);

DROP TRIGGER IF EXISTS trg_raw_files_updated_at ON raw_files;
CREATE TRIGGER trg_raw_files_updated_at
    BEFORE UPDATE ON raw_files
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_parsed_resumes_updated_at ON parsed_resumes;
CREATE TRIGGER trg_parsed_resumes_updated_at
    BEFORE UPDATE ON parsed_resumes
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_parsed_jds_updated_at ON parsed_jds;
CREATE TRIGGER trg_parsed_jds_updated_at
    BEFORE UPDATE ON parsed_jds
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- Extend raw_files.uploader_role to include recruiter (alias for admin)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'raw_files_uploader_role_check') THEN
        ALTER TABLE raw_files DROP CONSTRAINT raw_files_uploader_role_check;
    END IF;
    ALTER TABLE raw_files ADD CONSTRAINT raw_files_uploader_role_check
        CHECK (uploader_role IN ('candidate', 'admin', 'recruiter'));
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

-- -----------------------------------------------------------------------------
-- 9. interviews — scaffold for Interview AI
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    assigned_to VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
    status VARCHAR(20) NOT NULL DEFAULT 'Scheduled'
        CHECK (status IN ('Scheduled', 'Completed', 'Cancelled', 'Rescheduled')),
    scheduled_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    interview_type VARCHAR(50) NULL,
    location VARCHAR(255) NULL,
    notes TEXT NULL,
    feedback_toon TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL REFERENCES hr_signup(hrid),
    updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid)
);

CREATE INDEX IF NOT EXISTS IX_interviews_application ON interviews(application_id);
CREATE INDEX IF NOT EXISTS IX_interviews_assigned_scheduled ON interviews(assigned_to, scheduled_at);

DROP TRIGGER IF EXISTS trg_interviews_updated_at ON interviews;
CREATE TRIGGER trg_interviews_updated_at
    BEFORE UPDATE ON interviews
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 10. offers — scaffold for Offer AI
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    generated_by VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
    status VARCHAR(30) NOT NULL DEFAULT 'Draft'
        CHECK (status IN ('Draft', 'Pending Approval', 'Sent', 'Accepted', 'Rejected', 'Expired')),
    compensation_json JSONB NULL,
    letter_toon TEXT NULL,
    sent_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    responded_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL REFERENCES hr_signup(hrid),
    updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid)
);

CREATE INDEX IF NOT EXISTS IX_offers_application ON offers(application_id);
CREATE INDEX IF NOT EXISTS IX_offers_status_expires ON offers(status, expires_at);

DROP TRIGGER IF EXISTS trg_offers_updated_at ON offers;
CREATE TRIGGER trg_offers_updated_at
    BEFORE UPDATE ON offers
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- -----------------------------------------------------------------------------
-- 11. saved_jobs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_jobs (
    id SERIAL PRIMARY KEY,
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid) ON DELETE CASCADE,
    job_id VARCHAR(20) NOT NULL REFERENCES jobs(jdid) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (candidate_id, job_id)
);

CREATE INDEX IF NOT EXISTS IX_saved_jobs_candidate ON saved_jobs(candidate_id, saved_at DESC);

-- -----------------------------------------------------------------------------
-- 12. Child tables — surrogate primary keys
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_education' AND column_name = 'id'
    ) THEN
        ALTER TABLE candidate_education ADD COLUMN id SERIAL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'candidate_education_pkey') THEN
            ALTER TABLE candidate_education ADD PRIMARY KEY (id);
        END IF;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_certifications' AND column_name = 'id'
    ) THEN
        ALTER TABLE candidate_certifications ADD COLUMN id SERIAL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'candidate_certifications_pkey') THEN
            ALTER TABLE candidate_certifications ADD PRIMARY KEY (id);
        END IF;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_experiences' AND column_name = 'id'
    ) THEN
        ALTER TABLE candidate_experiences ADD COLUMN id SERIAL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'candidate_experiences_pkey') THEN
            ALTER TABLE candidate_experiences ADD PRIMARY KEY (id);
        END IF;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'hr_login' AND column_name = 'id'
    ) THEN
        ALTER TABLE hr_login ADD COLUMN id SERIAL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'hr_login_pkey') THEN
            ALTER TABLE hr_login ADD PRIMARY KEY (id);
        END IF;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'candidate_login' AND column_name = 'id'
    ) THEN
        ALTER TABLE candidate_login ADD COLUMN id SERIAL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'candidate_login_pkey') THEN
            ALTER TABLE candidate_login ADD PRIMARY KEY (id);
        END IF;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 13. login_history, support_requests, employee_feedback — audit extensions
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'login_history' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE login_history ADD COLUMN user_id VARCHAR(50) NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'support_requests' AND column_name = 'created_by'
    ) THEN
        ALTER TABLE support_requests ADD COLUMN created_by VARCHAR(50) NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'support_requests' AND column_name = 'updated_by'
    ) THEN
        ALTER TABLE support_requests ADD COLUMN updated_by VARCHAR(50) NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'employee_feedback' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE employee_feedback ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'employee_feedback' AND column_name = 'submitted_by'
    ) THEN
        ALTER TABLE employee_feedback ADD COLUMN submitted_by VARCHAR(20) NULL REFERENCES hr_signup(hrid);
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_employee_feedback_updated_at ON employee_feedback;
CREATE TRIGGER trg_employee_feedback_updated_at
    BEFORE UPDATE ON employee_feedback
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- =============================================================================
-- End of domain freeze migration
-- =============================================================================
-- <<< END 04_domain_freeze.sql

-- >>> BEGIN 05_remove_legacy_rbac.sql
-- =============================================================================
-- Sprint 1.3 — Remove legacy RBAC boolean columns and sync trigger
-- =============================================================================

DROP TRIGGER IF EXISTS trg_hr_signup_role_sync ON hr_signup;
DROP FUNCTION IF EXISTS hr_signup_role_sync();

ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_super_admin;
ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_head_hr;
ALTER TABLE hr_signup DROP COLUMN IF EXISTS is_ceo;
-- <<< END 05_remove_legacy_rbac.sql

-- >>> BEGIN 08_public_apply_purge_candidate_auth.sql
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
-- <<< END 08_public_apply_purge_candidate_auth.sql

-- >>> BEGIN 09_interview_ai_scheduling.sql
-- Interview scheduling + AI interviewer support (extends interviews scaffold)

ALTER TABLE interviews ALTER COLUMN assigned_to DROP NOT NULL;

ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
    CHECK (status IN ('Scheduled', 'InProgress', 'Completed', 'Cancelled', 'Rescheduled'));

ALTER TABLE interviews ADD COLUMN IF NOT EXISTS interviewer_type VARCHAR(20) NOT NULL DEFAULT 'ai';
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 30;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS invite_token VARCHAR(64);
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS meeting_link TEXT;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS questions_json JSONB;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS answers_json JSONB;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS overall_score NUMERIC(5,2);
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS score_summary TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'interviews_interviewer_type_check'
    ) THEN
        ALTER TABLE interviews
            ADD CONSTRAINT interviews_interviewer_type_check
            CHECK (interviewer_type IN ('human', 'ai'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS UX_interviews_invite_token
    ON interviews(invite_token)
    WHERE invite_token IS NOT NULL;
-- <<< END 09_interview_ai_scheduling.sql

-- >>> BEGIN 10_jobs_keywords.sql
-- Add keywords column to jobs for JD-derived search/match terms
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'jobs' AND column_name = 'keywords'
    ) THEN
        ALTER TABLE jobs ADD COLUMN keywords TEXT NULL;
    END IF;
END $$;
-- <<< END 10_jobs_keywords.sql

-- >>> BEGIN 14_interview_scheduling.sql
-- Interview scheduling: extend interviews, add interview_slots, per-recruiter Google OAuth

-- -----------------------------------------------------------------------------
-- interviews extensions
-- -----------------------------------------------------------------------------
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS calendar_event_id TEXT NULL;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS invite_expires_at TIMESTAMPTZ NULL;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS interviewer_hrid VARCHAR(20) NULL REFERENCES hr_signup(hrid);

ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
    CHECK (status IN ('Invited', 'Scheduled', 'InProgress', 'Completed', 'Cancelled', 'Rescheduled'));

CREATE UNIQUE INDEX IF NOT EXISTS UX_interviews_open_application
    ON interviews(application_id)
    WHERE status IN ('Invited', 'Scheduled');

-- -----------------------------------------------------------------------------
-- interview_slots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interview_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    recruiter_hrid VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_booked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS IX_interview_slots_interview_booked
    ON interview_slots(interview_id, is_booked);

CREATE INDEX IF NOT EXISTS IX_interview_slots_recruiter_start
    ON interview_slots(recruiter_hrid, start_time);

-- -----------------------------------------------------------------------------
-- oauth_tokens: per-recruiter Google Calendar
-- -----------------------------------------------------------------------------
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS hrid VARCHAR(20) NULL REFERENCES hr_signup(hrid);

ALTER TABLE oauth_tokens DROP CONSTRAINT IF EXISTS uq_oauth_tokens_company_provider;

CREATE UNIQUE INDEX IF NOT EXISTS UX_oauth_tokens_provider_hrid
    ON oauth_tokens(provider, hrid)
    WHERE hrid IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS UX_oauth_tokens_company_provider_no_hrid
    ON oauth_tokens(company_key, provider)
    WHERE hrid IS NULL;
-- <<< END 14_interview_scheduling.sql

-- >>> BEGIN 15_raw_files_blob.sql
-- Durable original upload bytes for resumes / JDs (PDF, DOCX, …)
-- Source of truth: Postgres. Disk MEDIA_ROOT remains an optional local cache.

ALTER TABLE raw_files
    ADD COLUMN IF NOT EXISTS file_data BYTEA NULL;

COMMENT ON COLUMN raw_files.file_data IS
    'Original uploaded file bytes (PDF/DOCX/…). Primary durable store.';
-- <<< END 15_raw_files_blob.sql
