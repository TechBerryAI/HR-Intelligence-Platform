# Alembic (Postgres) — HCIP

## Layout

| Path | Role |
|------|------|
| `schema_pg/01_core.sql` … `04_seeds.sql` | **Frozen baseline only** (applied by `20260806_0001` / `0002`) |
| `alembic/versions/` | **All new DDL** — incremental, reversible revisions |
| `app/database/schema_apply.py` | Loads `schema_pg` SQL (baseline revisions only) |

## Rules (Phase 5 freeze)

1. **Do not edit** `schema_pg/01–04` for feature work. Those files are the historical baseline.
2. Every schema change = `alembic revision -m "…"` with real `upgrade()` / `downgrade()`.
3. Prefer expand → migrate data → contract (nullable columns before drops).
4. Never use `CREATE TABLE IF NOT EXISTS` re-apply as the migration strategy for new changes.
5. App startup (`init_db`) runs `alembic upgrade head` only.

## Commands

```bash
cd apps/backend
alembic current
alembic upgrade head
alembic revision -m "add_foo_column"
# edit the new file under alembic/versions/
alembic upgrade head
alembic downgrade -1   # verify reversibility when safe
```

If you see `Can't locate revision identified by '…'`, an orphan stamp was left after a deleted revision file. `upgrade_head` / `init_db` auto-repair to `20260806_0001`, or manually:

```bash
alembic stamp 20260806_0001
alembic upgrade head
```

**Do not** add new numbered `NN_*.sql` under `app/database/migrations/` (legacy folder retired).

## Remediation chain (2026-08-07)

| Revision | Purpose |
|----------|---------|
| `20260806_0002` | No-op stamp bridge (full schema re-apply removed — it rolled back upgrades) |
| `20260807_0003` | Interviews `Invited` CHECK + applications status default |
| `20260807_0004` | Auth hygiene (drop `hr_login.password`, CID width, indexes) |
| `20260807_0005` | `organizations` + `organization_id` backfill |
| `20260807_0006` | Blob offload columns (`storage_backend`, `resume_raw_file_id`) |
| `20260807_0007` | `ux_matches_latest` + drop dead `saved_jobs` |
| `20260807_0008` | Platform scaffold (later dropped — was empty) |
| `20260807_0009` | Drop unused scaffold tables; keep `organizations` only |
| `20260807_0010` | Drop offers/events; merge hr_login→login_history; HRAuth→hr_signup |

Fresh empty DB: apply `schema_pg` via baseline `20260806_0001` (or `python -c` schema_apply), then `alembic upgrade head`.


## Blob offload

New uploads write bytes to `MEDIA_ROOT` (S3-swappable via `media_storage`).  
Legacy `raw_files.file_data` / profile BYTEA can be migrated with:

```bash
cd apps/backend
python -m app.database.scripts.offload_blobs --limit 100
```
