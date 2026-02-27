# Data Migration and Validation — SQL Server to PostgreSQL

## 5.1 Export from SQL Server

- Use **SQL Server Management Studio** or **sqlcmd** to export tables (e.g. CSV or use a ETL tool).
- Or use **pgloader** (e.g. `pgloader mssql://user:pass@host/JobPortal postgresql://user:pass@host/JobPortal`) to migrate schema + data.
- Or use a **Python script**: connect with pyodbc (read) and psycopg2 (write) in dependency order below.

## 5.2 Load order (after running `backend/schema_pg/01_schema.sql`)

1. hr_signup  
2. candidate_signup  
3. candidate_education, candidate_certifications, candidate_experiences  
4. hr_login, candidate_login  
5. jobs  
6. candidate_profiles  
7. applications  
8. support_requests  
9. raw_files, parsed_resumes, parsed_jds  
10. login_history  
11. CandidateAuth, HRAuth  

Then set the candidate CID sequence (so new signups get correct next CID):

```sql
SELECT setval('candidate_cid_seq', COALESCE((
  SELECT MAX(CAST(REGEXP_REPLACE(cid, '[^0-9]', '', 'g')::text AS INTEGER)) FROM candidate_signup
), 1));
```

For PostgreSQL 10+: if the max cid is 'CID042', use:

```sql
SELECT setval('candidate_cid_seq', (SELECT COALESCE(MAX(SUBSTRING(cid FROM '[0-9]+')::INT), 1) FROM candidate_signup));
```

## 5.3 Row-count validation (run on both DBs and diff)

```sql
-- SQL Server
SELECT 'hr_signup' AS tbl, COUNT(*) AS cnt FROM hr_signup
UNION ALL SELECT 'candidate_signup', COUNT(*) FROM candidate_signup
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL SELECT 'applications', COUNT(*) FROM applications
UNION ALL SELECT 'support_requests', COUNT(*) FROM support_requests
UNION ALL SELECT 'raw_files', COUNT(*) FROM raw_files
UNION ALL SELECT 'parsed_resumes', COUNT(*) FROM parsed_resumes
UNION ALL SELECT 'parsed_jds', COUNT(*) FROM parsed_jds
UNION ALL SELECT 'login_history', COUNT(*) FROM login_history
UNION ALL SELECT 'CandidateAuth', COUNT(*) FROM CandidateAuth
UNION ALL SELECT 'HRAuth', COUNT(*) FROM HRAuth;
```

```sql
-- PostgreSQL (same)
SELECT 'hr_signup' AS tbl, COUNT(*) AS cnt FROM hr_signup
UNION ALL SELECT 'candidate_signup', COUNT(*) FROM candidate_signup
UNION ALL SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL SELECT 'applications', COUNT(*) FROM applications
UNION ALL SELECT 'support_requests', COUNT(*) FROM support_requests
UNION ALL SELECT 'raw_files', COUNT(*) FROM raw_files
UNION ALL SELECT 'parsed_resumes', COUNT(*) FROM parsed_resumes
UNION ALL SELECT 'parsed_jds', COUNT(*) FROM parsed_jds
UNION ALL SELECT 'login_history', COUNT(*) FROM login_history
UNION ALL SELECT 'CandidateAuth', COUNT(*) FROM "CandidateAuth"
UNION ALL SELECT 'HRAuth', COUNT(*) FROM "HRAuth";
```

## 5.4 Checksum (spot-check critical tables)

```sql
-- Applications: MD5 of id + candidate_id + job_id + status (SQL Server)
SELECT SUM(CHECKSUM_AGG(CHECKSUM(id, candidate_id, job_id, status))) FROM applications;

-- PostgreSQL (approximate: use md5 concat)
SELECT SUM(('x' || SUBSTR(MD5(id::text || candidate_id || job_id || status), 1, 8))::bit(32)::bigint) FROM applications;
```

Or compare a few rows by primary key between the two databases.

## 5.5 Data validation checklist

- [ ] Row counts match for every table  
- [ ] No orphaned FKs (e.g. applications.job_id all exist in jobs)  
- [ ] Timestamps look correct (UTC)  
- [ ] Booleans: BIT 0/1 → false/true  
- [ ] UUIDs in raw_files / parsed_* are valid  
- [ ] candidate_profiles.resume BYTEA length matches source VARBINARY length for a sample  
