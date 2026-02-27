# PostgreSQL Migration — Validation Checklist

Use this after data migration and after switching the app to PostgreSQL.

## Data integrity
- [ ] Row counts match (run the row-count queries in `DATA_MIGRATION_AND_VALIDATION.md` on both DBs and diff).
- [ ] No orphaned FKs: `applications.job_id` ∈ `jobs.jdid`, `applications.candidate_id` ∈ `candidate_signup.cid`, etc.
- [ ] Spot-check a few rows: same PKs and key columns in both DBs.
- [ ] `candidate_cid_seq` set correctly (next insert gets expected CID).

## Workflows
- [ ] HR signup → OTP email → verify OTP → account in `hr_signup` → login.
- [ ] Candidate signup → OTP → verify → account in `candidate_signup` with CID → login.
- [ ] HR: create job, list jobs, get job, update job, toggle enabled, delete job.
- [ ] Candidate: get profile, save profile (with/without resume), get resume.
- [ ] Candidate: apply to job; application appears with status; ATS callback updates application when configured.
- [ ] HR: list applications for job, view candidate profile, download resume, update application status (shortlist/reject).
- [ ] Support: submit request (request_id returned), list by email, update status.
- [ ] Parsing: upload resume/JD, parse, get cached result by hash.
- [ ] Login history: failed/success recorded; recent failed count and same-device check work.

## Edge cases
- [ ] NULL in optional columns (email, phone, ats_reasoning, admin_notes).
- [ ] OTP expiry: expired OTP rejected; datetime comparison correct (PG returns timestamptz).
- [ ] Resume BYTEA: upload and download resume; size matches.
- [ ] Quoted column: `"cgpa/percentage"` in candidate_education (PG) and `[cgpa/percentage]` (MSSQL) both work when BACKEND is set correctly.

## Performance
- [ ] List jobs and list applications respond in acceptable time.
- [ ] No N+1 or missing indexes on hot paths (indexes are in `01_schema.sql`).

## Rollback
- [ ] If rollback: set `USE_POSTGRES=0` or remove `DATABASE_URL`; ensure `MSSQL_*` are set; restart app; confirm app talks to SQL Server again.
