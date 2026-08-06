-- =============================================================================
-- 01_core.sql — consolidated from: 01_schema.sql, 03_employee_feedback.sql
-- =============================================================================


-- >>> BEGIN 01_schema.sql
-- =============================================================================
-- HR Intelligence - PostgreSQL Schema (replaces SQL Server init_db + migrations)
-- =============================================================================
-- Run once against an empty database (e.g. psql -f 01_schema.sql).
-- Type mappings: NVARCHAR->VARCHAR/TEXT, DATETIME2->TIMESTAMPTZ, BIT->BOOLEAN,
--                UNIQUEIDENTIFIER->UUID, IDENTITY->SERIAL/IDENTITY, VARBINARY(MAX)->BYTEA.
-- =============================================================================

-- Extensions (optional, for gen_random_uuid() if not available in older PG)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. hr_signup
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hr_signup (
    hrid VARCHAR(20) NOT NULL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    company VARCHAR(255) NOT NULL,
    password VARCHAR(255) NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'RECRUITER'
        CHECK (role IN ('CEO', 'HEAD_HR', 'RECRUITER')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(20) NULL REFERENCES hr_signup(hrid)
);
CREATE INDEX IF NOT EXISTS IX_hr_signup_role ON hr_signup(role);

-- -----------------------------------------------------------------------------
-- 2. Sequence for candidate CID (CID001, CID002, ...)
-- -----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS candidate_cid_seq AS INTEGER START WITH 1 INCREMENT BY 1;

-- -----------------------------------------------------------------------------
-- 3. candidate_signup
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_signup (
    cid VARCHAR(20) NOT NULL PRIMARY KEY DEFAULT ('CID' || LPAD(nextval('candidate_cid_seq')::text, 3, '0')),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 4. candidate_education, candidate_certifications, candidate_experiences
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_education (
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid) ON DELETE CASCADE,
    degree VARCHAR(255),
    institution VARCHAR(255),
    "cgpa/percentage" VARCHAR(50),
    start_date VARCHAR(50),
    end_date VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS IX_candidate_education_candidate ON candidate_education(candidate_id);

CREATE TABLE IF NOT EXISTS candidate_certifications (
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid) ON DELETE CASCADE,
    certification VARCHAR(255),
    issuer VARCHAR(255),
    end_month VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS IX_candidate_certifications_candidate ON candidate_certifications(candidate_id);

CREATE TABLE IF NOT EXISTS candidate_experiences (
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid) ON DELETE CASCADE,
    company VARCHAR(255),
    role VARCHAR(255),
    start_date VARCHAR(50),
    end_date VARCHAR(50),
    present VARCHAR(10)
);
CREATE INDEX IF NOT EXISTS IX_candidate_experiences_candidate ON candidate_experiences(candidate_id);

-- -----------------------------------------------------------------------------
-- 5. hr_login, candidate_login
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hr_login (
    hrid VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    logged_in_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_hr_login_hrid ON hr_login(hrid);

-- candidate_login removed: applicants apply without accounts

-- -----------------------------------------------------------------------------
-- 6. jobs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    jdid VARCHAR(20) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    salary VARCHAR(255),
    experience VARCHAR(100),
    description TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    posted_by VARCHAR(20) NULL REFERENCES hr_signup(hrid),
    posted_on TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 7. candidate_profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_profiles (
    candidate_id VARCHAR(20) NOT NULL PRIMARY KEY REFERENCES candidate_signup(cid),
    full_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    experience_level VARCHAR(50),
    serving_notice VARCHAR(10),
    notice_period VARCHAR(50),
    last_working_day VARCHAR(50),
    linkedin_url VARCHAR(500),
    portfolio_url VARCHAR(500),
    current_location VARCHAR(255),
    preferred_location VARCHAR(255),
    resume BYTEA,
    completed BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 8. applications
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    candidate_id VARCHAR(20) NOT NULL REFERENCES candidate_signup(cid),
    job_id VARCHAR(20) NOT NULL REFERENCES jobs(jdid),
    status VARCHAR(50) DEFAULT 'pending',
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    matching_percentage FLOAT DEFAULT 0,
    match_score FLOAT NULL,
    shortlisted BOOLEAN NULL DEFAULT false,
    ats_reasoning TEXT NULL,
    ats_analysis TEXT NULL,
    UNIQUE (candidate_id, job_id)
);
CREATE INDEX IF NOT EXISTS IX_applications_shortlisted ON applications(shortlisted, match_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS IX_applications_status ON applications(status, applied_at DESC);

-- -----------------------------------------------------------------------------
-- 9. support_requests
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS support_requests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    user_id VARCHAR(50) NULL,
    user_type VARCHAR(20) NULL CHECK (user_type IN ('candidate', 'hr', 'guest') OR user_type IS NULL),
    subject VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ NULL,
    admin_notes TEXT NULL
);
CREATE INDEX IF NOT EXISTS IX_support_requests_email ON support_requests(email);
CREATE INDEX IF NOT EXISTS IX_support_requests_user_id ON support_requests(user_id);
CREATE INDEX IF NOT EXISTS IX_support_requests_status ON support_requests(status);
CREATE INDEX IF NOT EXISTS IX_support_requests_created_at ON support_requests(created_at DESC);

-- -----------------------------------------------------------------------------
-- 10. raw_files, parsed_resumes, parsed_jds (parsing workflow)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id VARCHAR(50) NOT NULL,
    uploader_role VARCHAR(20) NOT NULL CHECK (uploader_role IN ('candidate', 'admin', 'recruiter', 'public')),
    original_filename VARCHAR(255) NOT NULL,
    storage_url VARCHAR(1000) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL,
    file_data BYTEA NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (file_hash, uploader_id)
);
CREATE INDEX IF NOT EXISTS IX_raw_files_uploader ON raw_files(uploader_id, uploader_role);
CREATE INDEX IF NOT EXISTS IX_raw_files_hash ON raw_files(file_hash);
CREATE INDEX IF NOT EXISTS IX_raw_files_created_at ON raw_files(created_at DESC);

CREATE TABLE IF NOT EXISTS parsed_resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_file_id UUID NOT NULL REFERENCES raw_files(id) ON DELETE CASCADE,
    candidate_id VARCHAR(20) NULL REFERENCES candidate_signup(cid) ON DELETE SET NULL,
    toon TEXT NOT NULL,
    full_text TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_parsed_resumes_raw_file ON parsed_resumes(raw_file_id);
CREATE INDEX IF NOT EXISTS IX_parsed_resumes_candidate ON parsed_resumes(candidate_id);
CREATE INDEX IF NOT EXISTS IX_parsed_resumes_confidence ON parsed_resumes(confidence);
CREATE INDEX IF NOT EXISTS IX_parsed_resumes_created_at ON parsed_resumes(created_at DESC);

CREATE TABLE IF NOT EXISTS parsed_jds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_file_id UUID NOT NULL REFERENCES raw_files(id) ON DELETE CASCADE,
    job_id VARCHAR(20) NULL REFERENCES jobs(jdid) ON DELETE SET NULL,
    toon TEXT NOT NULL,
    full_text TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_parsed_jds_raw_file ON parsed_jds(raw_file_id);
CREATE INDEX IF NOT EXISTS IX_parsed_jds_job ON parsed_jds(job_id);
CREATE INDEX IF NOT EXISTS IX_parsed_jds_confidence ON parsed_jds(confidence);
CREATE INDEX IF NOT EXISTS IX_parsed_jds_created_at ON parsed_jds(created_at DESC);

-- -----------------------------------------------------------------------------
-- 11. login_history
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS login_history (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('HR', 'candidate')),
    ip_address VARCHAR(100),
    user_agent VARCHAR(500),
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed')),
    failure_reason VARCHAR(255),
    attempted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_login_history_email ON login_history(email, user_type);

-- -----------------------------------------------------------------------------
-- 12. HRAuth (OTP verification for staff signup)
-- -----------------------------------------------------------------------------
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
);
CREATE UNIQUE INDEX IF NOT EXISTS IX_HRAuth_Email ON "HRAuth"(email);

-- =============================================================================
-- End of schema
-- =============================================================================
-- <<< END 01_schema.sql

-- >>> BEGIN 03_employee_feedback.sql
-- -----------------------------------------------------------------------------
-- employee_feedback: Internal HRMS testing feedback (bugs, features, general)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS employee_feedback (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR(255) NOT NULL,
    employee_id VARCHAR(50) NULL,
    department VARCHAR(255) NULL,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('Bug Report', 'Feature Request', 'General Feedback', 'Appreciation')),
    module VARCHAR(255) NULL,
    severity VARCHAR(20) NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical') OR severity IS NULL),
    description TEXT NOT NULL,
    screenshot_path VARCHAR(1000) NULL,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'reviewed', 'resolved')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_created_at ON employee_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_feedback_type ON employee_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_module ON employee_feedback(module);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_status ON employee_feedback(status);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_severity ON employee_feedback(severity);
-- <<< END 03_employee_feedback.sql
