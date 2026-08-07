Legacy numbered SQL migrations were consolidated into `apps/backend/schema_pg/`:

- `01_core.sql`
- `02_domain.sql`
- `03_integrations.sql`
- `04_seeds.sql`

Schema is applied by Alembic (see `apps/backend/alembic/`).
Do not add new files here.
