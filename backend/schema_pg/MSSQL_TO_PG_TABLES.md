# MSSQL → PostgreSQL table/column alignment

This checklist ensures `01_schema.sql` matches your MSSQL `JobPortal.dbo` tables so everything works in pgAdmin.

## Tables verified from MSSQL (SSMS)

| MSSQL Table        | PG Table         | Columns match | Notes |
|--------------------|------------------|---------------|--------|
| dbo.hr_signup      | hr_signup        | ✓             | hrid, full_name, email, company, password, created_at |
| dbo.HRAuth          | "HRAuth"         | ✓             | Mixed-case: use double quotes in SQL. id, full_name, email, company, password_hash, otp, otp_expiry, is_verified, created_at, updated_at. BIT→BOOLEAN, DATETIME2→TIMESTAMPTZ. |
| dbo.CandidateAuth   | "CandidateAuth"  | ✓             | Mixed-case: use double quotes. Same type mappings as HRAuth. |
| dbo.jobs            | jobs             | ✓             | jdid, title, company, location, salary, experience, description, enabled, posted_by, posted_on. BIT→BOOLEAN, DATETIME2→TIMESTAMPTZ. |
| dbo.support_requests| support_requests | ✓             | id, name, email, user_id, user_type, subject, message, status, priority, created_at, updated_at, resolved_at, admin_notes |
| dbo.raw_files       | raw_files        | ✓             | id (UUID), uploader_id, uploader_role, original_filename, storage_url, mime_type, file_hash, size_bytes, created_at. UNIQUEIDENTIFIER→UUID. |
| dbo.parsed_resumes   | parsed_resumes   | ✓             | id, raw_file_id, candidate_id, toon, full_text, confidence, model_version, created_at |
| dbo.parsed_jds       | parsed_jds       | ✓             | id, raw_file_id, job_id, toon, full_text, confidence, model_version, created_at |
| dbo.login_history    | login_history    | ✓             | id, email, user_type, ip_address, user_agent, status, failure_reason, attempted_at. user_type CHECK: 'HR', 'candidate'. |
| dbo.hr_login         | hr_login         | ✓             | hrid, email, password, logged_in_at. FK to hr_signup(hrid). |
| dbo.candidate_login  | candidate_login  | ✓             | cid, email, password, logged_in_at. FK to candidate_signup(cid). |
| dbo.candidate_signup | candidate_signup | ✓             | cid, name, email, password, created_at. cid default from sequence (CID001, CID002, …). |
| dbo.candidate_profiles | candidate_profiles | ✓           | candidate_id, full_name, email, phone, experience_level, serving_notice, notice_period, last_working_day, linkedin_url, portfolio_url, current_location, preferred_location, resume (BYTEA), completed (BOOLEAN), updated_at. |
| dbo.candidate_education | candidate_education | ✓         | candidate_id, degree, institution, "cgpa/percentage", start_date, end_date. Column with slash must be quoted in PG. |
| dbo.candidate_experiences | candidate_experiences | ✓       | candidate_id, company, role, start_date, end_date, present. |
| dbo.candidate_certifications | candidate_certifications | ✓   | candidate_id, certification, issuer, end_month. All nullable except candidate_id. |
| dbo.applications  | applications     | ✓             | id, candidate_id, job_id, status, applied_at, matching_percentage, match_score, shortlisted (BOOLEAN), ats_reasoning, ats_analysis. UNIQUE(candidate_id, job_id). |

## Type mappings (used in schema)

- **NVARCHAR / VARCHAR** → VARCHAR(n) or TEXT  
- **DATETIME2** → TIMESTAMPTZ  
- **BIT** → BOOLEAN (use `true`/`false` in SQL, True/False in Python)  
- **UNIQUEIDENTIFIER** → UUID  
- **IDENTITY** → SERIAL or IDENTITY / sequence  
- **VARBINARY(MAX)** → BYTEA (or VARCHAR if stored as hex string, e.g. file_hash)  

## Tables in PG schema (for when you add “other tables”)

Already in `01_schema.sql` (grouped):  
Signup/auth: hr_signup, candidate_signup, hr_login, candidate_login, "CandidateAuth", "HRAuth". Candidate data: candidate_profiles, candidate_education, candidate_certifications, candidate_experiences. Jobs: jobs, applications. Support/logging: support_requests, login_history. Parsing: raw_files, parsed_resumes, parsed_jds.

No schema changes needed for pgAdmin; backend code already uses the correct table/column names and types for PostgreSQL.
