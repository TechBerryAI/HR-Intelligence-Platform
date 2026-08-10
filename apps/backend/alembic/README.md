# Alembic (Postgres) — HCIP

Alembic is the **only** source of truth for database schema changes.

## Layout

| Path | Role |
|------|------|
| `alembic/versions/` | Migration revisions (start with squashed baseline `20260810_s001`) |
| `alembic/baseline/` | SQL applied by the baseline revision only (do not edit for features) |
| `app/database/sql_apply.py` | Multi-statement SQL helper used by the baseline |

## Rules

1. Every schema change = `alembic revision -m "…"` with real `upgrade()` / `downgrade()`.
2. Prefer expand → migrate data → contract (nullable columns before drops).
3. Do **not** add parallel SQL schema trees or startup fallbacks that stamp `head` while skipping revisions.
4. App startup (`init_db`) runs `alembic upgrade head` only.

## Commands

```bash
cd apps/backend
alembic current
alembic upgrade head
alembic revision -m "add_foo_column"
# edit the new file under alembic/versions/
alembic upgrade head
```

### Fresh / local reset

Local DBs stamped at pre-squash revisions must be wiped once:

```bash
# drop + recreate database, then:
cd apps/backend
alembic upgrade head
```

If you see `Can't locate revision identified by '…'`, wipe/recreate the DB (preferred) or, for empty salvage only:

```bash
alembic stamp 20260810_s001
alembic upgrade head
```

**Do not** add numbered `NN_*.sql` under `app/database/migrations/` (legacy folder retired).

## Baseline

| Revision | Purpose |
|----------|---------|
| `20260810_s001` | Squashed full schema (formerly `schema_pg` + revisions through `20260810_0014`) |

## Catalog + media volume

Postgres = catalog (hashes, keys). Durable bytes: see **[docs/MEDIA_AND_BACKUPS.md](../../../docs/MEDIA_AND_BACKUPS.md)**.
