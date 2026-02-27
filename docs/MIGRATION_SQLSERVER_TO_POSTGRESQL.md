# HRMS Job Portal — SQL Server to PostgreSQL Migration

## 1. Migration Risk Report (Phase 1 — Full System Audit)

### 1.1 Summary

| Category | Finding | Risk |
|----------|---------|------|
| **Database driver** | `pyodbc` + ODBC Driver for SQL Server | **High** — Must switch to `psycopg2` (or `asyncpg`). Connection string and parameter style change. |
| **Parameter binding** | All queries use `?` placeholders (ODBC style) | **High** — PostgreSQL uses `%s`. Every raw SQL call must be updated or abstracted. |
| **ORM** | SQLAlchemy with `mssql+pyodbc://` | **Medium** — Change to `postgresql+psycopg2://`. Same models; dialect handles types. |
| **Stored procedures** | **None** — All logic in Python | **Low** — No T-SQL procedures to convert. |
| **Views / Triggers** | None in codebase | **Low** |
| **Schema creation** | In-app `init_db()` in `db.py` (large T-SQL block) | **High** — Full DDL is SQL Server–specific (IDENTITY, NVARCHAR, SYSUTCDATETIME, OBJECT_ID, COL_LENGTH, cursors, GO, etc.). Must be replaced with PostgreSQL DDL and a separate init/migration runner. |
| **Migrations** | `backend/migrations/*.sql` (001–004) use T-SQL | **Medium** — Recreate as PostgreSQL-compatible scripts or fold into schema. |
| **Raw SQL surface** | ~15+ files use `db_run` / `db_get` / `db_all` with raw SQL | **High** — Syntax and function substitutions required in each. |

---

### 1.2 MS SQL–Specific Syntax Identified

| Location | Syntax | PostgreSQL equivalent |
|----------|--------|------------------------|
| **db.py** (init_db) | `NVARCHAR(n)`, `NVARCHAR(MAX)` | `VARCHAR(n)`, `TEXT` |
| | `DATETIME2`, `SYSUTCDATETIME()` | `TIMESTAMP WITH TIME ZONE`, `NOW()` / `CURRENT_TIMESTAMP` |
| | `BIT` | `BOOLEAN` |
| | `INT IDENTITY(1,1)` | `SERIAL` or `GENERATED ALWAYS AS IDENTITY` |
| | `UNIQUEIDENTIFIER`, `NEWID()` | `UUID`, `gen_random_uuid()` |
| | `VARBINARY(MAX)` | `BYTEA` |
| | `OBJECT_ID('dbo.t', 'U')`, `COL_LENGTH()` | `to_regclass('public.t')` / `information_schema` |
| | `EXEC sp_rename`, `sp_executesql` | `ALTER TABLE ... RENAME COLUMN`; execute dynamic SQL via `EXECUTE` in PL/pgSQL or in app |
| | `GO` batch separator | Not used; run statements separately |
| | `SCOPE_IDENTITY()` | `RETURNING id` |
| | `[cgpa/percentage]` (bracket names) | `"cgpa/percentage"` (double-quote) |
| **support.py** | `SYSUTCDATETIME()`, `SCOPE_IDENTITY()` | `NOW()`, `RETURNING id` |
| **candidate.py** | `SYSUTCDATETIME()`, `LEN(resume)` | `NOW()`, `LENGTH(resume)` |
| | `pyodbc.Binary(resume_binary)` | Pass `bytes`; psycopg2 handles BYTEA |
| **jobs.py** | `SELECT TOP 1`, `ISNUMERIC(SUBSTRING(...))`, `LEN(?)` | `SELECT ... LIMIT 1`, `~ '^[0-9]+$'` or regex, `LENGTH(...)` |
| **routes/simple_candidate_auth.py** | `SYSUTCDATETIME()`, `SELECT TOP 1` | `NOW()`, `LIMIT 1` |
| **sessions_service.py** | `TOP (?)`, `DATEDIFF(MINUTE, ...)` | `LIMIT %s`, `EXTRACT(EPOCH FROM (NOW() - attempted_at))/60` |
| **auth.py** | Datetime parsing for SQL Server format | Same Python logic; PG returns timestamp with time zone (consistent). |
| **applications.py** | Parameter placeholders `?` | `%s` |
| **parsing_utils.py** | `?` placeholders; UUIDs as strings | `%s`; UUID type in PG. |

---

### 1.3 Tables and Dependencies (Logical Order for Creation)

1. **hr_signup** (no FK)
2. **candidate_cid_seq** (sequence)
3. **candidate_signup** (uses sequence for default cid)
4. **candidate_education**, **candidate_certifications**, **candidate_experiences** (FK → candidate_signup)
5. **hr_login** (FK → hr_signup)
6. **candidate_login** (FK → candidate_signup)
7. **jobs** (FK → hr_signup)
8. **candidate_profiles** (FK → candidate_signup)
9. **applications** (FK → candidate_signup, jobs)
10. **support_requests** (standalone)
11. **raw_files** (standalone)
12. **parsed_resumes** (FK → raw_files, candidate_signup)
13. **parsed_jds** (FK → raw_files, jobs)
14. **login_history** (standalone)
15. **CandidateAuth**, **HRAuth** (standalone)

---

### 1.4 Constraints and Indexes to Preserve

- **Primary keys** on all tables.
- **Unique**: hr_signup(email), candidate_signup(email), CandidateAuth(email), HRAuth(email), UQ_application (candidate_id, job_id), UQ_raw_files_hash_uploader (file_hash, uploader_id).
- **Foreign keys** with ON DELETE CASCADE or SET NULL as per current design.
- **Check constraints**: support_requests (status, priority, user_type), raw_files (uploader_role), login_history (user_type, status).
- **Indexes**: All existing indexes on FKs and commonly filtered columns (e.g. applications shortlisted/status, support_requests status/created_at, login_history email/user_type).

---

### 1.5 Identity / Auto-Generated Values

- **applications.id**: INT IDENTITY → SERIAL / IDENTITY.
- **support_requests.id**: INT IDENTITY → SERIAL / IDENTITY.
- **login_history.id**: INT IDENTITY → SERIAL / IDENTITY.
- **CandidateAuth.id**, **HRAuth.id**: INT IDENTITY → SERIAL / IDENTITY.
- **candidate_signup.cid**: Default from sequence `'CID' || LPAD(nextval('candidate_cid_seq')::text, 3, '0')` (equivalent to FORMAT(NEXT VALUE FOR ..., '000')).
- **raw_files.id**, **parsed_resumes.id**, **parsed_jds.id**: UNIQUEIDENTIFIER DEFAULT NEWID() → UUID DEFAULT gen_random_uuid().

---

### 1.6 Known Application Quirks

- **saved_jobs**: Referenced in `jobs.py` (update_job) but table is dropped in migrations. Migration should remove the `UPDATE saved_jobs` line or guard with “table exists” to avoid errors on PG.
- **admin/routes.py**: Uses `j.created_at`; jobs table has `posted_on`. Fix to `posted_on` for consistency (applies to both MSSQL and PG).
- **db_run** return value: Code expects `lastID` when using `SCOPE_IDENTITY()`. With PG use `RETURNING id` and read from result to preserve behavior (e.g. support request submit).

---

## 2. PostgreSQL Schema Scripts (Phase 2)

See `backend/schema_pg/01_schema.sql` for full DDL. Summary of type mappings:

- **IDENTITY / SERIAL**: All integer PKs use `GENERATED ALWAYS AS IDENTITY` or `SERIAL`.
- **NVARCHAR → VARCHAR/TEXT**: String columns; use TEXT where MAX was used.
- **DATETIME2 → TIMESTAMPTZ**: All datetime columns.
- **BIT → BOOLEAN**.
- **UNIQUEIDENTIFIER → UUID**.
- **VARBINARY(MAX) → BYTEA** (candidate_profiles.resume).
- **Default timestamps**: `SYSUTCDATETIME()` → `CURRENT_TIMESTAMP` (or `NOW()`).
- **Bracket-quoted column** `[cgpa/percentage]` → `"cgpa/percentage"` in PostgreSQL.

---

## 3. Logic & Procedure Migration (Phase 3)

- **Stored procedures**: None in the project; no conversion needed.
- **init_db() in db.py**: No longer runs T-SQL. For PostgreSQL:
  - Use `01_schema.sql` to create schema (run once, e.g. via psql or a small script).
  - Optionally keep a small “migration runner” that runs `backend/schema_pg/*.sql` in order if you add more files later.
- **Transaction and error handling**: Keep current Python pattern (commit/rollback in context manager). psycopg2 supports this the same way.

---

## 4. Backend Refactor (Phase 4)

- **db.py**: Replace pyodbc with psycopg2; connection string from env (POSTGRES_* or DATABASE_URL); use `%s` for parameters; implement `lastID` via `RETURNING` where needed.
- **models/__init__.py**: Set SQLAlchemy URL to `postgresql+psycopg2://...`.
- **All modules** that call `db_run`/`db_get`/`db_all`: Replace `?` with `%s` in SQL strings; replace T-SQL functions (SYSUTCDATETIME, SCOPE_IDENTITY, TOP, LEN, ISNUMERIC, SUBSTRING/LEN for jdid, DATEDIFF) with PostgreSQL equivalents as in the table above.
- **candidate.py**: Use `NOW()` (or pass from app), `LENGTH(resume)`; remove `pyodbc.Binary`, pass raw bytes.
- **support.py**: Single-statement INSERT with `RETURNING id`; use `%s` and `NOW()`.
- **jobs.py**: Remove or guard `UPDATE saved_jobs`; fix jdid query to use PostgreSQL-compatible expression and `LIMIT 1`.
- **sessions_service.py**: `LIMIT %s`, and replace `DATEDIFF(MINUTE, attempted_at, SYSUTCDATETIME()) < ?` with `(EXTRACT(EPOCH FROM (NOW() - attempted_at)) / 60)::int < %s` or equivalent.
- **env_validator.py** / **app.py** / **README**: Document new env vars (e.g. POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_PORT); remove MSSQL-specific checks.

---

## 5. Data Migration Strategy (Phase 5)

### 5.1 Export from SQL Server

- **Option A**: Use SSMS / `sqlcmd` / BCP to export data (e.g. CSV or native format) per table.
- **Option B**: Use a migration tool (e.g. pgloader, or custom Python script with pyodbc read + psycopg2 write) to stream data in dependency order.

### 5.2 Order of Load (after creating PG schema)

1. hr_signup  
2. candidate_signup (ensure sequence is set after load: `SELECT setval('candidate_cid_seq', (SELECT MAX(CAST(SUBSTRING(cid FROM '[0-9]+') AS INT)) FROM candidate_signup));`)  
3. candidate_education, candidate_certifications, candidate_experiences  
4. hr_login, candidate_login  
5. jobs  
6. candidate_profiles  
7. applications  
8. support_requests  
9. raw_files, parsed_resumes, parsed_jds  
10. login_history  
11. CandidateAuth, HRAuth  

### 5.3 Data Validation Checklist

- Row counts match per table (e.g. `SELECT COUNT(*) FROM table` on both sides).
- Spot-check PKs and FKs (no orphaned rows).
- Timestamps in UTC; compare a sample of rows.
- Boolean/BIT columns: 0/1 → false/true.
- UUIDs: same format in PG (lowercase with hyphens).
- BYTEA (resume): spot-check length and first bytes.

### 5.4 Row-Count and Checksum Scripts

- **Row counts**: Run `SELECT 'table_name', COUNT(*) FROM table_name` for each table in both DBs and diff.
- **Checksums**: For critical tables (e.g. applications, candidate_signup), checksum by id and a few key columns (e.g. MD5(concat(id, candidate_id, job_id))) and compare.

---

## 6. Regression & Performance Validation (Phase 6)

### 6.1 Test Queries to Validate

- Auth: HR signup → verify OTP → login; candidate signup → verify OTP → login.
- Jobs: Create job, list jobs, get job, update job, toggle enabled, delete job.
- Applications: Candidate applies; HR lists applications; ATS callback updates application.
- Candidate profile: Get profile, save profile (with and without resume), get resume.
- Support: Submit request, list by email, update status.
- Parsing: Upload resume/JD, parse, fetch cached result.
- Sessions / login history: Record login, get history, failed-attempt count.

### 6.2 Index Optimization for PostgreSQL

- Add indexes on columns used in WHERE and JOIN (already reflected in schema).
- Consider BRIN for very large time-ordered tables (e.g. login_history, applications) if needed.
- Use `EXPLAIN (ANALYZE, BUFFERS)` on heavy queries and compare with SQL Server plans if needed.

### 6.3 Null and Edge Cases

- Explicitly test: NULL in optional columns (email, phone, ats_reasoning, etc.).
- Empty string vs NULL where app logic differs.
- OTP expiry and datetime parsing (PG returns timestamptz; ensure Python still compares correctly).

---

## 7. Deployment Plan (Summary)

1. **Pre-migration**: Backup SQL Server DB; create PG database and role; apply `01_schema.sql`.
2. **Data migration**: Run export/transform/load in table order; set sequences; run row-count and checksum validation.
3. **Backend**: Deploy refactored code (db.py, models, all SQL to %s and PG functions); set POSTGRES_* (or DATABASE_URL) in env; remove MSSQL env and ODBC dependency.
4. **Smoke tests**: Run the test queries above; run any existing integration/API tests.
5. **Cutover**: Switch app to PG; monitor errors and performance; keep SQL Server backup until validated.
6. **Cleanup**: Remove pyodbc, MSSQL docs, and init_db T-SQL from codebase; update README and runbooks.

---

---

## 8. Final Deployment Plan (Step-by-Step)

1. **Pre-migration**
   - Backup SQL Server database (full backup or export critical tables).
   - Create PostgreSQL database and user (e.g. `createdb JobPortal`, create role with password).
   - Run `backend/schema_pg/01_schema.sql` on the empty PostgreSQL database (e.g. `psql -h host -U user -d JobPortal -f backend/schema_pg/01_schema.sql`).

2. **Data migration**
   - Export data from SQL Server in dependency order (see §5.2 in this doc and `docs/DATA_MIGRATION_AND_VALIDATION.md`).
   - Import into PostgreSQL (pgloader, custom script, or ETL).
   - Set `candidate_cid_seq`: run the `setval` statement from `backend/schema_pg/README.md`.

3. **Backend configuration**
   - Set in `backend/.env` either:
     - `USE_POSTGRES=1` and `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, **or**
     - `DATABASE_URL=postgresql://user:password@host:5432/JobPortal`
   - Install deps: `pip install -r backend/requirements.txt` (includes `psycopg2-binary`).
   - Do **not** set `MSSQL_*` when using PostgreSQL; env validator will accept POSTGRES/DATABASE_URL when `USE_POSTGRES` or `DATABASE_URL` is set.

4. **Run application**
   - Start backend: from repo root or `backend`, run the Flask app (e.g. `python -m flask run` or your start script).
   - App will load `db_pg` and use PostgreSQL for all DB access and SQLAlchemy (HRAuth/CandidateAuth).

5. **Smoke tests**
   - Health: `GET /health`
   - HR signup → verify OTP → login.
   - Candidate signup → verify OTP → login.
   - Create job, list jobs, apply to job, view applications (with ATS fields if configured).
   - Support: submit request, list by email, update status.
   - Run row-count validation (see `docs/DATA_MIGRATION_AND_VALIDATION.md`).

6. **Cutover and cleanup**
   - Point production to PostgreSQL; monitor errors and performance.
   - Keep SQL Server backup until validation is complete.
   - Optionally remove `pyodbc` and MSSQL-specific docs later; code supports both via env.

---

*End of Migration Report. See `backend/schema_pg/01_schema.sql` for PostgreSQL DDL; `backend/db_pg.py` and the listed backend files for refactored code.*
