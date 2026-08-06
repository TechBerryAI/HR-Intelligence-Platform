# Alembic (Postgres) — HCIP

## Layout

| Path | Role |
|------|------|
| `schema_pg/01_core.sql` … `04_seeds.sql` | Consolidated schema source of truth |
| `alembic/versions/` | Versioned migrations (apply / evolve schema) |
| `app/database/schema_apply.py` | Loads `schema_pg` SQL (used by baseline revisions) |

## Commands

```bash
cd apps/backend
alembic current
alembic upgrade head
alembic revision -m "add_foo_column"
# edit the new file under alembic/versions/
alembic upgrade head
```

App startup (`init_db`) runs `alembic upgrade head` only.

If you see `Can't locate revision identified by '…'`, an orphan stamp was left after a deleted revision file. `upgrade_head` / `init_db` auto-repair to `20260806_0001`, or manually:

```bash
alembic stamp 20260806_0001
alembic upgrade head
```

**Do not** add new numbered `NN_*.sql` under `app/database/migrations/` (legacy folder retired).
