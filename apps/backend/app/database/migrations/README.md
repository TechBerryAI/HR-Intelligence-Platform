# Database migrations

Legacy numbered SQL under this folder was retired.

**Source of truth:** Alembic under [`apps/backend/alembic/`](../../alembic/).

```bash
cd apps/backend
alembic upgrade head
alembic revision -m "describe_change"
```

See [`alembic/README.md`](../../alembic/README.md).
