# PostgreSQL schema for HR Job Portal

Run the schema once against an empty PostgreSQL database:

```bash
psql -h localhost -U your_user -d JobPortal -f 01_schema.sql
```

Or set `PGPASSWORD` and use connection string. After loading existing data from SQL Server, set the candidate CID sequence to avoid conflicts:

```sql
SELECT setval('candidate_cid_seq', COALESCE((
  SELECT MAX(CAST(SUBSTRING(cid FROM '[0-9]+') AS INTEGER)) FROM candidate_signup
), 1));
```
